"""
IRSA helpers — build IAM roles trusted by the cluster's OIDC provider, scoped
to a specific (namespace, service-account) pair.

How it works:
- Each EKS cluster exposes an OIDC issuer (a URL like
  https://oidc.eks.eu-west-3.amazonaws.com/id/ABCDEF...).
- We register that issuer in IAM as an OpenID Connect provider.
- For each pod that needs AWS perms, we create an IAM role whose trust policy
  says: "anyone presenting a JWT signed by THIS issuer, with sub=
  system:serviceaccount:<ns>:<sa> and aud=sts.amazonaws.com, may assume me."
- The pod's projected service account token is exactly such a JWT.
- The AWS SDK in the pod automatically calls sts:AssumeRoleWithWebIdentity
  with the token, gets temporary credentials, and forgets the role exists.

Result: each pod has its own least-privilege IAM identity instead of sharing
the EC2 instance profile of the node it happens to run on.
"""

import json
from typing import List, Optional

import pulumi
import pulumi_aws as aws


def _trust_policy(
    oidc_provider_arn: pulumi.Output[str],
    oidc_provider_url: pulumi.Output[str],
    namespace: str,
    service_account: str,
) -> pulumi.Output[str]:
    """Build a trust policy for one specific (namespace, service-account)."""

    def _build(args):
        arn, url = args
        return json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"Federated": arn},
                        "Action": "sts:AssumeRoleWithWebIdentity",
                        "Condition": {
                            "StringEquals": {
                                # Pin the role to one exact ServiceAccount.
                                f"{url}:sub": (
                                    f"system:serviceaccount:{namespace}:{service_account}"
                                ),
                                # And reject tokens issued for any other audience.
                                f"{url}:aud": "sts.amazonaws.com",
                            }
                        },
                    }
                ],
            }
        )

    return pulumi.Output.all(oidc_provider_arn, oidc_provider_url).apply(_build)


def irsa_role(
    name: str,
    oidc_provider_arn: pulumi.Output[str],
    oidc_provider_url: pulumi.Output[str],
    namespace: str,
    service_account: str,
    managed_policy_arns: Optional[List[str]] = None,
    inline_policy: Optional[dict] = None,
) -> aws.iam.Role:
    """Create an IRSA-trusted role with optional managed and/or inline policies."""
    role = aws.iam.Role(
        f"{name}-irsa",
        assume_role_policy=_trust_policy(
            oidc_provider_arn, oidc_provider_url, namespace, service_account
        ),
    )
    for i, arn in enumerate(managed_policy_arns or []):
        aws.iam.RolePolicyAttachment(
            f"{name}-irsa-attach-{i}",
            role=role.name,
            policy_arn=arn,
        )
    if inline_policy is not None:
        aws.iam.RolePolicy(
            f"{name}-irsa-inline",
            role=role.id,
            policy=json.dumps(inline_policy),
        )
    return role
