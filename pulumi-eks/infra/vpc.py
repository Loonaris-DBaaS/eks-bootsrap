"""
VPC layer.

Design decisions:
- One VPC (10.0.0.0/16), 3 AZs (eu-west-3a, eu-west-3b, eu-west-3c).
- Public-only subnets. We intentionally do NOT provision a NAT Gateway, and
  we don't need private subnets either: workers run in the public subnets
  with public IPs so the IGW handles their egress.
- EKS requires subnets in at least 2 AZs — we use 3 for higher availability.
- EKS-required subnet tags are applied so the cluster can discover them and
  the AWS Load Balancer Controller can place public ELBs correctly.
"""

from dataclasses import dataclass
from typing import List

import pulumi
import pulumi_aws as aws


@dataclass
class VpcOutputs:
    vpc_id: pulumi.Output[str]
    public_subnet_ids: List[pulumi.Output[str]]


# 3 AZs in eu-west-3. /20 blocks = 4091 usable IPs each.
AZS = ["eu-west-3a", "eu-west-3b", "eu-west-3c"]
PUBLIC_CIDRS = ["10.0.0.0/20", "10.0.16.0/20", "10.0.32.0/20"]


def build_vpc(cluster_name: str) -> VpcOutputs:
    vpc = aws.ec2.Vpc(
        "vpc",
        cidr_block="10.0.0.0/16",
        enable_dns_hostnames=True,
        enable_dns_support=True,
        tags={"Name": f"{cluster_name}-vpc"},
    )

    # One IGW per VPC. Attaching it does NOT by itself give any subnet
    # internet access — the route table must also send 0.0.0.0/0 to it.
    igw = aws.ec2.InternetGateway(
        "igw",
        vpc_id=vpc.id,
        tags={"Name": f"{cluster_name}-igw"},
    )

    # Public route table: default route -> IGW. Any subnet associated with
    # this table becomes a "public" subnet.
    public_rt = aws.ec2.RouteTable(
        "public-rt",
        vpc_id=vpc.id,
        routes=[
            aws.ec2.RouteTableRouteArgs(
                cidr_block="0.0.0.0/0", gateway_id=igw.id
            )
        ],
        tags={"Name": f"{cluster_name}-public-rt"},
    )

    public_subnets: List[aws.ec2.Subnet] = []

    for idx, az in enumerate(AZS):
        pub = aws.ec2.Subnet(
            f"public-{az}",
            vpc_id=vpc.id,
            cidr_block=PUBLIC_CIDRS[idx],
            availability_zone=az,
            map_public_ip_on_launch=True,
            tags={
                "Name": f"{cluster_name}-public-{az}",
                "kubernetes.io/role/elb": "1",
                f"kubernetes.io/cluster/{cluster_name}": "shared",
            },
        )
        aws.ec2.RouteTableAssociation(
            f"public-rta-{az}",
            subnet_id=pub.id,
            route_table_id=public_rt.id,
        )
        public_subnets.append(pub)

    return VpcOutputs(
        vpc_id=vpc.id,
        public_subnet_ids=[s.id for s in public_subnets],
    )
