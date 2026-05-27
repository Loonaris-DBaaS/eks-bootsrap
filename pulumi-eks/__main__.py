"""
Pulumi entrypoint — wires VPC, IAM, EKS cluster, OIDC/IRSA, node groups,
and addons together.

Run:
    pulumi up
"""

import pulumi

from infra.cluster import (
    build_cluster,
    build_node_group,
    build_oidc_provider,
    install_addons,
)
from infra.iam import cluster_role, node_role
from infra.irsa import irsa_role
from infra.kubeconfig import render_kubeconfig
from infra.vpc import build_vpc

CLUSTER_NAME = "loonaris-db-cluster"
REGION = "eu-west-3"

# 1. Network — VPC + 3 public subnets + IGW + public route table.
vpc = build_vpc(CLUSTER_NAME)

# 2. IAM — control-plane role + worker-node role.
ctrl_role = cluster_role(CLUSTER_NAME)
nodes_role = node_role(CLUSTER_NAME)

# 3. EKS control plane. Subnets are public; control-plane ENIs land there too.
cluster = build_cluster(
    CLUSTER_NAME,
    ctrl_role.arn,
    vpc.public_subnet_ids,
)

# 4. OIDC provider — required before any IRSA-consuming addon (EBS CSI).
oidc = build_oidc_provider(CLUSTER_NAME, cluster)
oidc_url = cluster.identities[0].oidcs[0].issuer.apply(
    lambda i: i.replace("https://", "")
)

# 5. IRSA role for the EBS CSI controller.
ebs_csi_irsa = irsa_role(
    "ebs-csi",
    oidc.arn,
    oidc_url,
    namespace="kube-system",
    service_account="ebs-csi-controller-sa",
    managed_policy_arns=[
        "arn:aws:iam::aws:policy/service-role/AmazonEBSCSIDriverPolicy"
    ],
)

# 6. Managed node groups — both in public subnets so workers get public IPs.
system_ng = build_node_group(
    resource_name="system",
    cluster=cluster,
    node_role_arn=nodes_role.arn,
    subnet_ids=vpc.public_subnet_ids,
    desired=2,
    labels={"role": "system", "pool": "system"},
    instance_types=["t3.small"],
)

workload_ng = build_node_group(
    resource_name="workload",
    cluster=cluster,
    node_role_arn=nodes_role.arn,
    subnet_ids=vpc.public_subnet_ids,
    desired=3,
    labels={"role": "worker", "pool": "workload", "workload": "database"},
    taints=[{"key": "dedicated", "value": "workload", "effect": "NO_SCHEDULE"}],
)

# 7. Cluster addons — depend on at least one node group so daemonset/
#    deployment pods can actually schedule.
install_addons(
    CLUSTER_NAME,
    cluster,
    ebs_csi_role_arn=ebs_csi_irsa.arn,
    depends_on=[system_ng, workload_ng],
)

# 8. IRSA roles for cluster-level controllers the operator will install
#    later via Helm/manifests. We only create the IAM side here.

cert_manager_irsa = irsa_role(
    "cert-manager",
    oidc.arn,
    oidc_url,
    namespace="cert-manager",
    service_account="cert-manager",
    inline_policy={
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "route53:GetChange",
                    "route53:ChangeResourceRecordSets",
                    "route53:ListResourceRecordSets",
                    "route53:ListHostedZonesByName",
                ],
                "Resource": "*",
            }
        ],
    },
)

external_dns_irsa = irsa_role(
    "external-dns",
    oidc.arn,
    oidc_url,
    namespace="external-dns",
    service_account="external-dns",
    inline_policy={
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": ["route53:ChangeResourceRecordSets"],
                "Resource": "arn:aws:route53:::hostedzone/*",
            },
            {
                "Effect": "Allow",
                "Action": [
                    "route53:ListHostedZones",
                    "route53:ListResourceRecordSets",
                    "route53:ListTagsForResource",
                ],
                "Resource": "*",
            },
        ],
    },
)

# AWS Load Balancer Controller — official upstream IAM policy embedded inline.
# Source: https://raw.githubusercontent.com/kubernetes-sigs/aws-load-balancer-controller/main/docs/install/iam_policy.json
alb_inline_policy = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "iam:CreateServiceLinkedRole",
                "ec2:DescribeAccountAttributes",
                "ec2:DescribeAddresses",
                "ec2:DescribeAvailabilityZones",
                "ec2:DescribeInternetGateways",
                "ec2:DescribeVpcs",
                "ec2:DescribeVpcPeeringConnections",
                "ec2:DescribeSubnets",
                "ec2:DescribeSecurityGroups",
                "ec2:DescribeInstances",
                "ec2:DescribeNetworkInterfaces",
                "ec2:DescribeTags",
                "ec2:GetCoipPoolUsage",
                "ec2:DescribeCoipPools",
                "elasticloadbalancing:DescribeLoadBalancers",
                "elasticloadbalancing:DescribeLoadBalancerAttributes",
                "elasticloadbalancing:DescribeListeners",
                "elasticloadbalancing:DescribeListenerCertificates",
                "elasticloadbalancing:DescribeSSLPolicies",
                "elasticloadbalancing:DescribeRules",
                "elasticloadbalancing:DescribeTargetGroups",
                "elasticloadbalancing:DescribeTargetGroupAttributes",
                "elasticloadbalancing:DescribeTargetHealth",
                "elasticloadbalancing:DescribeTags",
                "elasticloadbalancing:DescribeTrustStores",
                "elasticloadbalancing:DescribeListenerAttributes",
            ],
            "Resource": "*",
        },
        {
            "Effect": "Allow",
            "Action": [
                "cognito-idp:DescribeUserPoolClient",
                "acm:ListCertificates",
                "acm:DescribeCertificate",
                "iam:ListServerCertificates",
                "iam:GetServerCertificate",
                "waf-regional:GetWebACL",
                "waf-regional:GetWebACLForResource",
                "waf-regional:AssociateWebACL",
                "waf-regional:DisassociateWebACL",
                "wafv2:GetWebACL",
                "wafv2:GetWebACLForResource",
                "wafv2:AssociateWebACL",
                "wafv2:DisassociateWebACL",
                "shield:GetSubscriptionState",
                "shield:DescribeProtection",
                "shield:CreateProtection",
                "shield:DeleteProtection",
            ],
            "Resource": "*",
        },
        {
            "Effect": "Allow",
            "Action": [
                "ec2:AuthorizeSecurityGroupIngress",
                "ec2:RevokeSecurityGroupIngress",
                "ec2:CreateSecurityGroup",
                "ec2:CreateTags",
                "ec2:DeleteTags",
                "ec2:DeleteSecurityGroup",
                "elasticloadbalancing:CreateLoadBalancer",
                "elasticloadbalancing:CreateTargetGroup",
                "elasticloadbalancing:CreateListener",
                "elasticloadbalancing:DeleteListener",
                "elasticloadbalancing:CreateRule",
                "elasticloadbalancing:DeleteRule",
                "elasticloadbalancing:AddTags",
                "elasticloadbalancing:RemoveTags",
                "elasticloadbalancing:ModifyLoadBalancerAttributes",
                "elasticloadbalancing:SetIpAddressType",
                "elasticloadbalancing:SetSecurityGroups",
                "elasticloadbalancing:SetSubnets",
                "elasticloadbalancing:DeleteLoadBalancer",
                "elasticloadbalancing:ModifyTargetGroup",
                "elasticloadbalancing:ModifyTargetGroupAttributes",
                "elasticloadbalancing:DeleteTargetGroup",
                "elasticloadbalancing:ModifyListenerAttributes",
                "elasticloadbalancing:RegisterTargets",
                "elasticloadbalancing:DeregisterTargets",
                "elasticloadbalancing:SetWebAcl",
                "elasticloadbalancing:ModifyListener",
                "elasticloadbalancing:AddListenerCertificates",
                "elasticloadbalancing:RemoveListenerCertificates",
                "elasticloadbalancing:ModifyRule",
            ],
            "Resource": "*",
        },
    ],
}

alb_irsa = irsa_role(
    "aws-load-balancer-controller",
    oidc.arn,
    oidc_url,
    namespace="kube-system",
    service_account="aws-load-balancer-controller",
    inline_policy=alb_inline_policy,
)

# 9. Stack outputs.
kubeconfig = render_kubeconfig(cluster, REGION)

pulumi.export("cluster_name", cluster.name)
pulumi.export("cluster_endpoint", cluster.endpoint)
pulumi.export("oidc_provider_arn", oidc.arn)
pulumi.export("kubeconfig", pulumi.Output.secret(kubeconfig))
pulumi.export("cert_manager_role_arn", cert_manager_irsa.arn)
pulumi.export("external_dns_role_arn", external_dns_irsa.arn)
pulumi.export("alb_controller_role_arn", alb_irsa.arn)
