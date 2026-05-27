"""
IAM roles for the EKS control plane and managed node groups.

Two roles are created here:

1. Cluster role  — assumed by the EKS service itself (principal: eks.amazonaws.com).
                   Lets the EKS control plane manage ENIs, ELBs, security groups,
                   etc., in YOUR account on YOUR behalf.

2. Node role     — assumed by EC2 worker instances (principal: ec2.amazonaws.com).
                   Lets kubelet talk to EKS, pull images from ECR, run the VPC
                   CNI, manage EBS volumes, and accept SSM session connections.

Both roles use AWS-managed policies for predictability and forward-compatibility
when AWS extends EKS features.
"""

import json

import pulumi_aws as aws


def _assume_role_policy(service: str) -> str:
    """Build a trust policy allowing a given AWS service to assume the role."""
    return json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"Service": service},
                    "Action": "sts:AssumeRole",
                }
            ],
        }
    )


def cluster_role(name: str) -> aws.iam.Role:
    """IAM role assumed by the EKS control plane."""
    role = aws.iam.Role(
        f"{name}-cluster-role",
        assume_role_policy=_assume_role_policy("eks.amazonaws.com"),
    )
    aws.iam.RolePolicyAttachment(
        f"{name}-cluster-AmazonEKSClusterPolicy",
        role=role.name,
        policy_arn="arn:aws:iam::aws:policy/AmazonEKSClusterPolicy",
    )
    return role


def node_role(name: str) -> aws.iam.Role:
    """IAM role assumed by EC2 worker instances in managed node groups."""
    role = aws.iam.Role(
        f"{name}-node-role",
        assume_role_policy=_assume_role_policy("ec2.amazonaws.com"),
    )
    for suffix, arn in [
        # kubelet ↔ EKS API, node registration, etc.
        ("WorkerNode", "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy"),
        # AWS VPC CNI: manage ENIs and secondary IPs on the instance.
        ("CNI", "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy"),
        # Pull container images from any ECR repo in this account.
        ("ECR", "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"),
        # SSM Session Manager — connect to nodes without opening SSH.
        ("SSM", "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"),
        # EBS CSI driver running on the node (the controller uses an IRSA role).
        ("EBS", "arn:aws:iam::aws:policy/service-role/AmazonEBSCSIDriverPolicy"),
    ]:
        aws.iam.RolePolicyAttachment(
            f"{name}-node-{suffix}",
            role=role.name,
            policy_arn=arn,
        )
    return role
