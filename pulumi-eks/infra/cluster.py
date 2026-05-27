"""
EKS cluster, OIDC provider, managed node groups, and addons.

Design decisions:
- Control plane has BOTH public and private endpoints enabled.
- OIDC provider is created explicitly so IRSA roles (EBS CSI, cert-manager,
  external-dns, ALB controller) can be built before the addons that need them.
- A custom Launch Template gives node groups gp3 30 GiB encrypted root
  volumes (defaults are gp2 / 20 GiB) plus IMDSv2-required hardening.
- VPC CNI is configured with prefix delegation so t3.small can host
  ~110 pods/node instead of the default ~11.
"""

from typing import List, Optional

import pulumi
import pulumi_aws as aws


# Latest stable EKS-supported Kubernetes minor.
EKS_VERSION = "1.34"


def build_cluster(
    name: str,
    cluster_role_arn: pulumi.Output[str],
    subnet_ids: List[pulumi.Output[str]],
) -> aws.eks.Cluster:
    return aws.eks.Cluster(
        name,
        name=name,
        version=EKS_VERSION,
        role_arn=cluster_role_arn,
        vpc_config=aws.eks.ClusterVpcConfigArgs(
            subnet_ids=subnet_ids,
            endpoint_public_access=True,
            endpoint_private_access=True,
        ),
    )


def build_oidc_provider(
    name: str, cluster: aws.eks.Cluster
) -> aws.iam.OpenIdConnectProvider:
    """Register the cluster's OIDC issuer with IAM so it can sign IRSA tokens."""
    # AWS root CA thumbprint used by all EKS OIDC issuers — well-known constant.
    thumbprint = "9e99a48a9960b14926bb7f3b02e22da2b0ab7280"
    return aws.iam.OpenIdConnectProvider(
        f"{name}-oidc",
        client_id_lists=["sts.amazonaws.com"],
        thumbprint_lists=[thumbprint],
        url=cluster.identities[0].oidcs[0].issuer,
    )


def _launch_template(name: str) -> aws.ec2.LaunchTemplate:
    """gp3 30 GiB encrypted root volume + IMDSv2 required.

    Floor is 20 GiB (EKS-optimized AMI snapshot size); we provision 30 GiB
    for headroom for images/logs.
    """
    return aws.ec2.LaunchTemplate(
        f"{name}-lt",
        block_device_mappings=[
            aws.ec2.LaunchTemplateBlockDeviceMappingArgs(
                device_name="/dev/xvda",
                ebs=aws.ec2.LaunchTemplateBlockDeviceMappingEbsArgs(
                    volume_size=30,
                    volume_type="gp3",
                    delete_on_termination="true",
                    encrypted="true",
                ),
            )
        ],
        metadata_options=aws.ec2.LaunchTemplateMetadataOptionsArgs(
            http_tokens="required",
            # Hop limit 2 keeps kubelet/host happy but blocks the default
            # bridge-network pod path to IMDS, reducing blast radius.
            http_put_response_hop_limit=2,
        ),
        tag_specifications=[
            aws.ec2.LaunchTemplateTagSpecificationArgs(
                resource_type="instance",
                tags={"Name": f"{name}-node"},
            )
        ],
    )


def build_node_group(
    *,
    resource_name: str,
    cluster: aws.eks.Cluster,
    node_role_arn: pulumi.Output[str],
    subnet_ids: List[pulumi.Output[str]],
    desired: int,
    labels: dict,
    taints: Optional[list] = None,
    instance_types: Optional[List[str]] = None,
) -> aws.eks.NodeGroup:
    lt = _launch_template(resource_name)
    return aws.eks.NodeGroup(
        resource_name,
        cluster_name=cluster.name,
        node_role_arn=node_role_arn,
        subnet_ids=subnet_ids,  # public subnets — workers get public IPs
        instance_types=instance_types or ["t3.small"],
        scaling_config=aws.eks.NodeGroupScalingConfigArgs(
            desired_size=desired, min_size=desired, max_size=desired
        ),
        labels=labels,
        taints=[
            aws.eks.NodeGroupTaintArgs(
                key=t["key"], value=t["value"], effect=t["effect"]
            )
            for t in (taints or [])
        ],
        launch_template=aws.eks.NodeGroupLaunchTemplateArgs(
            id=lt.id,
            version=lt.latest_version.apply(lambda v: str(v)),
        ),
    )


def install_addons(
    name: str,
    cluster: aws.eks.Cluster,
    ebs_csi_role_arn: pulumi.Output[str],
    depends_on: list,
) -> None:
    """Install VPC CNI (with prefix delegation), CoreDNS, kube-proxy, EBS CSI."""

    aws.eks.Addon(
        f"{name}-vpc-cni",
        cluster_name=cluster.name,
        addon_name="vpc-cni",
        resolve_conflicts_on_create="OVERWRITE",
        resolve_conflicts_on_update="OVERWRITE",
        configuration_values=(
            '{"env":{"ENABLE_PREFIX_DELEGATION":"true","WARM_PREFIX_TARGET":"1"}}'
        ),
        opts=pulumi.ResourceOptions(depends_on=depends_on),
    )

    aws.eks.Addon(
        f"{name}-coredns",
        cluster_name=cluster.name,
        addon_name="coredns",
        resolve_conflicts_on_create="OVERWRITE",
        resolve_conflicts_on_update="OVERWRITE",
        opts=pulumi.ResourceOptions(depends_on=depends_on),
    )

    aws.eks.Addon(
        f"{name}-kube-proxy",
        cluster_name=cluster.name,
        addon_name="kube-proxy",
        resolve_conflicts_on_create="OVERWRITE",
        resolve_conflicts_on_update="OVERWRITE",
        opts=pulumi.ResourceOptions(depends_on=depends_on),
    )

    aws.eks.Addon(
        f"{name}-ebs-csi",
        cluster_name=cluster.name,
        addon_name="aws-ebs-csi-driver",
        service_account_role_arn=ebs_csi_role_arn,
        resolve_conflicts_on_create="OVERWRITE",
        resolve_conflicts_on_update="OVERWRITE",
        opts=pulumi.ResourceOptions(depends_on=depends_on),
    )
