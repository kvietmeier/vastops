"""
VAST Cluster Resource Reporter
Retrieves and prints Quotas, Views, VIP Pools, Tenants, and Users 
from the VAST cluster using the official vastpy SDK.
"""

import sys
# Import the initialization function from your custom module
from vast_init import get_vast_client

def list_cluster_resources():
    try:
        # 1. Initialize the official vastpy client
        client = get_vast_client()
        print("✅ Successfully authenticated via vastpy.")

        # ==========================================
        # 2. VIP POOLS
        # ==========================================
        print("\n" + "="*80)
        print(" VAST CLUSTER VIP POOLS")
        print("="*80)
        vip_pools = client.vip_pools.get()
        if vip_pools:
            for pool in vip_pools:
                p_id = pool.get('id', 'N/A')
                p_name = pool.get('name', 'N/A')
                p_role = pool.get('role', 'N/A')
                p_subnet = pool.get('subnet_cidr', 'N/A')
                # Format with wide, fixed columns for perfect alignment
                print(f"ID: {p_id:<6} | Name: {p_name:<25} | Role: {p_role:<15} | Subnet: {p_subnet}")
        else:
            print("No VIP Pools found.")

        # ==========================================
        # 3. TENANTS
        # ==========================================
        print("\n" + "="*80)
        print(" VAST CLUSTER TENANTS")
        print("="*80)
        tenants = client.tenants.get()
        if tenants:
            for tenant in tenants:
                t_id = tenant.get('id', 'N/A')
                t_name = tenant.get('name', 'N/A')
                print(f"ID: {t_id:<6} | Name: {t_name}")
        else:
            print("No Tenants found.")

        # ==========================================
        # 4. USERS
        # ==========================================
        print("\n" + "="*80)
        print(" VAST CLUSTER USERS")
        print("="*80)
        users = client.users.get()
        if users:
            for user in users:
                u_id = user.get('id', 'N/A')
                u_name = user.get('name', 'N/A')
                # uid is the system user ID (e.g., 1000)
                u_uid = user.get('uid', 'N/A') 
                print(f"ID: {u_id:<6} | Name: {u_name:<25} | System UID: {u_uid}")
        else:
            print("No Users found.")

        # ==========================================
        # 5. QUOTAS
        # ==========================================
        print("\n" + "="*80)
        print(" VAST CLUSTER QUOTAS")
        print("="*80)
        quotas = client.quotas.get()
        if quotas:
            for quota in quotas:
                q_id = quota.get('id', 'N/A')
                q_path = quota.get('path', 'N/A')
                q_limit = quota.get('hard_limit', 'No Limit')
                # Increased path width to 50 to accommodate long k8s PVC names
                print(f"ID: {q_id:<6} | Path: {q_path:<50} | Hard Limit: {q_limit}")
        else:
            print("No quotas found.")

        # ==========================================
        # 6. VIEWS (VOLUMES)
        # ==========================================
        print("\n" + "="*80)
        print(" VAST CLUSTER VIEWS (VOLUMES)")
        print("="*80)
        views = client.views.get()
        if views:
            for view in views:
                v_id = view.get('id', 'N/A')
                v_name = view.get('name', 'N/A')
                v_path = view.get('path', 'N/A')
                
                protocols = view.get('protocols', [])
                v_protocols = ", ".join(protocols) if isinstance(protocols, list) else protocols
                
                # Increased Name to 45 and Path to 50 for massive strings
                print(f"ID: {v_id:<7} | Name: {v_name:<45} | Path: {v_path:<50} | Protocols: {v_protocols}")
        else:
            print("No views found.")

    except Exception as e:
        print(f"\n❌ Error communicating with VAST API: {e}")
        sys.exit(1)

if __name__ == "__main__":
    list_cluster_resources()