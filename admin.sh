#!/bin/bash

# --- HELPERS -----------------------------------------------------------------

nodes_table() {
  local output=""
  for node in $(kubectl get nodes --no-headers -o jsonpath='{range .items[*]}{.metadata.name}{"\n"}{end}'); do
    printf ".. fetching %-60s\r" "$node" > /dev/tty
    role=$(kubectl get node $node -o jsonpath='{.metadata.labels.role}')
    instance=$(kubectl get node $node -o jsonpath='{.metadata.labels.node\.kubernetes\.io/instance-type}')
    zone=$(kubectl get node $node -o jsonpath='{.metadata.labels.topology\.kubernetes\.io/zone}')
    max=$(kubectl get node $node -o jsonpath='{.status.allocatable.pods}')
    memory=$(kubectl get node $node -o jsonpath='{.status.allocatable.memory}')
    cpu=$(kubectl get node $node -o jsonpath='{.status.allocatable.cpu}')
    status=$(kubectl get node $node -o jsonpath='{.status.conditions[-1].type}')
    used=$(kubectl get pods -A --field-selector spec.nodeName=$node --no-headers 2>/dev/null | wc -l | tr -d ' ')
    free=$((max - used))
    output="$output\n$node $role $instance $zone $max $used $free $memory $cpu $status"
  done
  printf "%-60s\r" "" > /dev/tty
  echo -e "NODE ROLE INSTANCE ZONE MAX USED FREE MEMORY CPU STATUS\n---- ---- -------- ---- --- ---- ---- ------ --- ------$output" | column -t
}

pods_for_nodes() {
  local selector=$1
  local nodes

  if [ "$selector" = "all" ]; then
    nodes=$(kubectl get nodes --no-headers -o jsonpath='{range .items[*]}{.metadata.name}{"\n"}{end}')
  else
    # supports any label selector e.g. pool=workload, role=system
    nodes=$(kubectl get nodes -l $selector -o jsonpath='{.items[*].metadata.name}' | tr ' ' '\n')
  fi

  if [ -z "$nodes" ]; then
    echo "[ERR] no nodes found for selector: $selector"
    return
  fi

  for node in $nodes; do
    echo ""
    echo "+-- Node: $node"
    kubectl get pods -A --field-selector spec.nodeName=$node
    echo ""
  done
}

pods_submenu() {
  while true; do
    echo ""
    echo "+--------------------------------------+"
    echo "|         Pods - Filter by             |"
    echo "+--------------------------------------+"
    echo "|  1) All nodes                        |"
    echo "|  2) Pool  -> workload                |"
    echo "|  3) Pool  -> system                  |"
    echo "|  4) Role  -> worker                  |"
    echo "|  5) Role  -> system                  |"
    echo "|  b) Back                             |"
    echo "+--------------------------------------+"
    echo -n "  Choose: "
    read sub

    case $sub in
      1) pods_for_nodes "all" ;;
      2) pods_for_nodes "pool=workload" ;;
      3) pods_for_nodes "pool=system" ;;
      4) pods_for_nodes "role=worker" ;;
      5) pods_for_nodes "role=system" ;;
      b) break ;;
      *) echo "[ERR] invalid option" ;;
    esac
  done
}

# --- MAIN MENU ----------------------------------------------------------------

while true; do
  echo ""
  echo "+--------------------------------------+"
  echo "|     loonaris-db-cluster CLI          |"
  echo "+--------------------------------------+"
  echo "|  1) Node overview                    |"
  echo "|  2) Pods ->                          |"
  echo "|  q) Quit                             |"
  echo "+--------------------------------------+"
  echo -n "  Choose: "
  read choice

  case $choice in
    1) echo "" && nodes_table ;;
    2) pods_submenu ;;
    q) echo "bye" && exit 0 ;;
    *) echo "[ERR] invalid option" ;;
  esac
done