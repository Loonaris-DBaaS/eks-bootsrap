# EKS Bootstrap Guide

This repository contains an `eksctl` cluster definition in `cluster<version>.yaml`.

## 0. Connect To Cluster (Developer First)

Use this first if the cluster already exists.

Check cluster state:

```bash
aws eks describe-cluster --region eu-west-3 --name loonaris-db-cluster --query 'cluster.status' --output text
```

If result is `ACTIVE`, connect kubeconfig:

```bash
aws eks update-kubeconfig --region eu-west-3 --name loonaris-db-cluster
kubectl get nodes
kubectl get pods -A
```

If result is `ResourceNotFoundException`, create the cluster (see Step 2).

Cluster details from current config:

- Cluster name: `loonaris-db-cluster`
- Region: `eu-west-3`
- Kubernetes version: `1.32`

## 1. Prerequisites

Install and configure:

- `aws` CLI (authenticated to your AWS account)
- `eksctl`
- `kubectl`

Quick checks:

```bash
aws sts get-caller-identity
eksctl version
kubectl version --client
```

Developer note:

- If the cluster already exists, do not run the create command again.
- You can check first with:

```bash
aws eks describe-cluster --region eu-west-3 --name loonaris-db-cluster --query 'cluster.status' --output text
```

If the command returns `ACTIVE`, skip Step 2 and go directly to Step 3.

## 2. Deploy The Cluster

From this repository root:

```bash
eksctl create cluster -f cluster.yaml
```

Optional pre-check before create:

```bash
eksctl create cluster -f cluster.yaml --dry-run
```

## 3. Connect A User To The Cluster

### Option A: Current AWS identity (same machine/user)

`eksctl` usually updates kubeconfig during creation. To refresh manually:

```bash
aws eks update-kubeconfig --region eu-west-3 --name loonaris-db-cluster
```

Verify access:

```bash
kubectl get nodes
kubectl get pods -A
```

### Option B: Another IAM user/role

1. Ensure that IAM principal has EKS access (recommended: EKS Access Entries).
2. On that user machine, run:

```bash
aws eks update-kubeconfig --region eu-west-3 --name loonaris-db-cluster
kubectl get nodes
```

If access is denied, add the principal to the cluster using EKS access management, then retry.

## 4. Delete The Cluster

Delete everything created by this config:

```bash
eksctl delete cluster -f cluster.yaml
```

If needed, you can also delete by name and region:

```bash
eksctl delete cluster --name loonaris-db-cluster --region eu-west-3
```

## 5. Troubleshooting

- `only 0 zones discovered`: instance type not available in selected AZs.
- `AccessDenied`: missing IAM permissions for EKS/EC2/CloudFormation/IAM.
- `kubectl` cannot connect: rerun `aws eks update-kubeconfig ...` and verify AWS credentials/profile.
