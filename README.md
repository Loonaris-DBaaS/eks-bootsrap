# EKS Bootstrap — loonaris-db-cluster

Cluster definition and infrastructure-as-code (IaC) for the loonaris EKS cluster on AWS (`eu-west-3`) using **Pulumi** (Python).

| | |
|---|---|
| Cluster | `loonaris-db-cluster` |
| Region | `eu-west-3` |
| Kubernetes | `1.35` |

## Architecture

This project provisions the following AWS infrastructure:
1. **Network**: A custom VPC with public subnets, an Internet Gateway, and a public route table.
2. **IAM**: Roles for the EKS control plane and worker nodes.
3. **Control Plane**: The EKS cluster itself.
4. **OIDC Provider**: Required for IAM Roles for Service Accounts (IRSA).
5. **Addons & IRSA**: 
   - VPC CNI, CoreDNS, kube-proxy.
   - EBS CSI Driver (via EKS Addons + IRSA role).
   - AWS Load Balancer Controller IRSA role.
   - Cert-Manager, External-DNS IRSA roles ready.

## Prerequisites

- `aws` CLI — authenticated (`aws sts get-caller-identity`).
- `pulumi` CLI.
- `python3` and `venv`.
- `kubectl`.

---

## 1. Setup Environment

Navigate to the IaC directory and prepare the Python environment:

```bash
cd pulumi-eks
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## 2. Deploy Infrastructure

Run Pulumi to preview and execute the changes:

```bash
cd pulumi-eks
pulumi up
```

> **Note:** The script may take 15-20 minutes to spin up the VPC, EKS Control Plane, and Node Groups.

---

## 3. Connect to the Cluster

Once Pulumi finishes, you can configure your `kubectl` easily using the AWS CLI:

```bash
aws eks update-kubeconfig --region eu-west-3 --name loonaris-db-cluster
kubectl get nodes
```

Alternatively, `pulumi up` generates a `kubeconfig.yaml` file natively at `pulumi-eks/kubeconfig.yaml`.

---

## 4. Install CloudNativePG

After the cluster is running, install the CNPG operator:

```bash
# Return to root directory
cd ..
bash install-cnpg.sh
```

---

## 5. Teardown

To destroy the cluster and all associated resources:

```bash
cd pulumi-eks
pulumi destroy
```
