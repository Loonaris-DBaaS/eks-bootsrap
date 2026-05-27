"""
Render a kubeconfig from cluster outputs.

We don't use aws-iam-authenticator (deprecated). Instead the kubeconfig
calls `aws eks get-token` via the `exec` plugin, which uses whatever
local AWS credentials the operator has configured.
"""

import json

import pulumi
import pulumi_aws as aws


def render_kubeconfig(cluster: aws.eks.Cluster, region: str) -> pulumi.Output[str]:
    return pulumi.Output.all(
        cluster.endpoint,
        cluster.certificate_authority.apply(lambda ca: ca.data),
        cluster.name,
    ).apply(
        lambda args: json.dumps(
            {
                "apiVersion": "v1",
                "kind": "Config",
                "clusters": [
                    {
                        "name": args[2],
                        "cluster": {
                            "server": args[0],
                            "certificate-authority-data": args[1],
                        },
                    }
                ],
                "contexts": [
                    {
                        "name": args[2],
                        "context": {"cluster": args[2], "user": args[2]},
                    }
                ],
                "current-context": args[2],
                "users": [
                    {
                        "name": args[2],
                        "user": {
                            "exec": {
                                "apiVersion": "client.authentication.k8s.io/v1beta1",
                                "command": "aws",
                                "args": [
                                    "--region",
                                    region,
                                    "eks",
                                    "get-token",
                                    "--cluster-name",
                                    args[2],
                                ],
                            }
                        },
                    }
                ],
            },
            indent=2,
        )
    )