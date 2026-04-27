# EKS Bootstrap — loonaris-db-cluster

Cluster definition and admin tooling for the loonaris EKS cluster on AWS (`eu-west-3`).

| | |
|---|---|
| Cluster | `loonaris-db-cluster` |
| Region | `eu-west-3` |
| Kubernetes | `1.35` |

## Versions

All versions are pinned — never `latest` in production.

| Component | Version | Notes |
|---|---|---|
| Kubernetes | `1.35` | Latest EKS release (Jan 2026), standard support until ~Mar 2027 |
| vpc-cni | `v1.21.1-eksbuild.7` | Latest patch for 1.35 |
| coredns | `v1.14.2-eksbuild.4` | Latest available for 1.35 |
| kube-proxy | `v1.35.3-eksbuild.5` | Tracks Kubernetes minor version |
| aws-ebs-csi-driver | `v1.59.0-eksbuild.1` | Latest stable |
| CloudNativePG | `1.29.0` | Latest stable (Apr 2026) |
| Calico (Tigera operator) | `v3.29.x` | Policy-only mode — VPC CNI handles networking |

Versions sourced from `aws eks describe-addon-versions --kubernetes-version 1.35` and the [CloudNativePG releases page](https://cloudnative-pg.io/releases/).

---

## 0. Already running? Connect first

```bash
aws eks describe-cluster \
  --region eu-west-3 \
  --name loonaris-db-cluster \
  --query 'cluster.status' --output text
```

If `ACTIVE`, update kubeconfig and verify:

```bash
aws eks update-kubeconfig --region eu-west-3 --name loonaris-db-cluster
kubectl get nodes
kubectl get pods -A
```

If `ResourceNotFoundException`, proceed to Step 2.

---

## 1. Prerequisites

- `aws` CLI — authenticated (`aws sts get-caller-identity`)
- `eksctl`
- `kubectl`

---

## 2. Create the cluster

```bash
eksctl create cluster -f clusterv1-t3.small.yaml
```

Dry-run first if needed:

```bash
eksctl create cluster -f clusterv1-t3.small.yaml --dry-run
```

> Do not run create if the cluster already exists.

---

## 3. Configure access and install operators

Copy the env template and fill in values:

```bash
cp .env.example .env
```

`.env` variables:

| Variable | Description |
|---|---|
| `AWS_REGION` | AWS region of the cluster |
| `CLUSTER_NAME` | EKS cluster name |
| `AWS_ACCOUNT_ID` | 12-digit AWS account ID |
| `CLUSTER_USERS` | Comma-separated IAM usernames to grant admin access |

Then run:

```bash
bash admin-config.sh
```

This script does four things:

1. **EKS access entries** — creates an access entry and attaches `AmazonEKSClusterAdminPolicy` for each user in `CLUSTER_USERS`
2. **aws-auth ConfigMap** — patches `mapUsers` in `kube-system/aws-auth` to grant `system:masters` via the legacy ConfigMap path (keeps `mapRoles` untouched)
3. **Calico** — installs the Tigera operator and applies `calico/calico-install.yaml` (policy-only mode)
4. **CloudNativePG** — installs the CNPG operator (`release-1.29`)

---

## 4. Developer kubeconfig setup

Each user runs this on their own machine:

```bash
aws eks update-kubeconfig --region eu-west-3 --name loonaris-db-cluster
kubectl get nodes
```

---

## 5. Delete the cluster

```bash
eksctl delete cluster -f clusterv1-t3.small.yaml
```

Or by name:

```bash
eksctl delete cluster --name loonaris-db-cluster --region eu-west-3
```

---

## 6. Troubleshooting

- `only 0 zones discovered` — instance type not available in the selected AZs, adjust the cluster yaml.
- `AccessDenied` — missing IAM permissions for EKS / EC2 / CloudFormation / IAM.
- `kubectl` cannot connect — rerun `aws eks update-kubeconfig ...` and verify AWS credentials.
- User can't access cluster after script — confirm both access entry (Step 3.1) and `aws-auth` patch (Step 3.2) succeeded in the script output.

