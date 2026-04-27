#!/bin/bash

if [ -f ".env" ]; then
  set -a
  . ./.env
  set +a
else
  echo "[ERR] .env file not found. Copy .env.example to .env and fill values."
  exit 1
fi

if [ -z "$AWS_REGION" ] || [ -z "$CLUSTER_NAME" ] || [ -z "$AWS_ACCOUNT_ID" ] || [ -z "$CLUSTER_USERS" ]; then
  echo "[ERR] Missing required variables. Ensure AWS_REGION, CLUSTER_NAME, AWS_ACCOUNT_ID and CLUSTER_USERS are set in .env."
  exit 1
fi

IFS=',' read -r -a users_names <<< "$CLUSTER_USERS"
account="$AWS_ACCOUNT_ID"

# the eks cluster uses the API mode and ConfigMap you can check it by this command:
# aws eks describe cluster --name loonaris-db-cluster --region eu-west-3 --query 'cluster.accessConfig'
# let's make the users access the cluster using the aws console:
for USER in "${users_names[@]}"; do
  echo "adding user $USER to the cluster access..."
  aws eks create-access-entry \
    --cluster-name "$CLUSTER_NAME" \
    --region "$AWS_REGION" \
    --principal-arn arn:aws:iam::$account:user/$USER
  aws eks associate-access-policy \
    --cluster-name "$CLUSTER_NAME" \
    --principal-arn arn:aws:iam::$account:user/$USER \
    --policy-arn arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy \
    --access-scope type=cluster \
    --region "$AWS_REGION"

  echo "Done: $USER"
done

# patch aws-auth ConfigMap so the IAM users also get kubectl access via legacy ConfigMap mode
echo "Patching aws-auth ConfigMap..."
tmp=$(mktemp)
printf 'data:\n  mapUsers: |\n' > "$tmp"
for USER in "${users_names[@]}"; do
  printf '    - userarn: arn:aws:iam::%s:user/%s\n' "$account" "$USER" >> "$tmp"
  printf '      username: %s\n'                                "$USER" >> "$tmp"
  printf '      groups:\n'                                             >> "$tmp"
  printf '      - system:masters\n'                                    >> "$tmp"
done
kubectl patch cm aws-auth -n kube-system --patch-file "$tmp"
rm -f "$tmp"
echo "aws-auth ConfigMap updated."

# installing Calico (policy-only mode — VPC CNI keeps control of networking)
echo "Installing Tigera operator..."
kubectl create -f https://raw.githubusercontent.com/projectcalico/calico/v3.29.3/manifests/tigera-operator.yaml
echo "Applying Calico Installation CR..."
kubectl apply -f calico/calico-install.yaml
echo "Calico installed."

#installing CloudNativePG
echo "Installing CloudNativePG operator..."
kubectl apply --server-side -f \
  https://raw.githubusercontent.com/cloudnative-pg/cloudnative-pg/release-1.29/releases/cnpg-1.29.0.yaml
