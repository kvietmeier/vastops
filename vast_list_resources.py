"""
VAST Cluster Resource Reporter (Parameterized)
By default, retrieves VIP Pools, Tenants, Users, and View Policies.
Optionally retrieves Views if the --views flag is provided.
Optionally retrieves Quotas if the --quotas flag is provided.
"""

import sys
import argparse
from vast_api_init import get_vast_client

def parse_arguments():
    """
    Sets up the command-line arguments for the script.
    """
    parser = argparse.ArgumentParser(description="VAST Cluster Resource Reporter")
    
    parser.add_argument(
        '--views', 
        action='store_true', 
        help="Include Views (Volumes) in the output"
    )
    
    parser.add_argument(
        '--quotas', 
        action='store_true', 
        help="Include Quotas in the output"
    )
    
    return parser.parse_args()

def list_cluster_resources():
    # 1. Parse the command-line arguments
    args = parse_arguments()

    try:
        # 2. Initialize the official vastpy client
        client = get_vast_client()
        print("✅ Successfully authenticated via vastpy.")
    except Exception as e:
        print(f"\n❌ Error authenticating with VAST API: {e}")
        sys.exit(1)

    # ==========================================
    # 3. VIP POOLS (Default)
    # ==========================================
    print("\n" + "="*80)
    print(" VAST CLUSTER VIP POOLS")
    print("="*80)
    try:
        vip_pools = client.vippools.get()
        if vip_pools:
            for pool in vip_pools:
                p_id = pool.get('id', 'N/A')
                p_name = pool.get('name', 'N/A')
                # Restoring Role and Subnet
                p_role = pool.get('role', 'N/A')
                p_subnet = pool.get('subnet_cidr', 'N/A')
                print(f"ID: {p_id:<6} | Name: {p_name:<25} | Role: {p_role:<25} | Subnet: {p_subnet}")
        else:
            print("No VIP Pools found.")
    except Exception as e:
        print(f"⚠️ Could not fetch VIP Pools: {e}")

    # ==========================================
    # 4. TENANTS (Default)
    # ==========================================
    print("\n" + "="*80)
    print(" VAST CLUSTER TENANTS")
    print("="*80)
    try:
        tenants = client.tenants.get()
        if tenants:
            for tenant in tenants:
                t_id = tenant.get('id', 'N/A')
                t_name = tenant.get('name', 'N/A')
                print(f"ID: {t_id:<6} | Name: {t_name}")
        else:
            print("No Tenants found.")
    except Exception as e:
        print(f"⚠️ Could not fetch Tenants: {e}")

    # ==========================================
    # 5. USERS (Default)
    # ==========================================
    print("\n" + "="*80)
    print(" VAST CLUSTER USERS")
    print("="*80)
    try:
        users = client.users.get()
        if users:
            for user in users:
                u_id = user.get('id', 'N/A')
                u_name = user.get('name', 'N/A')
                # Restoring System UID
                u_uid = user.get('uid', 'N/A') 
                print(f"ID: {u_id:<6} | Name: {u_name:<25} | System UID: {u_uid}")
        else:
            print("No Users found.")
    except Exception as e:
        print(f"⚠️ Could not fetch Users: {e}")

    # ==========================================
    # 6. VIEW POLICIES (Default)
    # ==========================================
    print("\n" + "="*80)
    print(" VAST CLUSTER VIEW POLICIES")
    print("="*80)
    try:
        policies = client.viewpolicies.get()
        if policies:
            for policy in policies:
                pol_id = policy.get('id', 'N/A')
                pol_name = policy.get('name', 'N/A')
                print(f"ID: {pol_id:<6} | Name: {pol_name}")
        else:
            print("No View Policies found.")
    except Exception as e:
        print(f"⚠️ Could not fetch View Policies: {e}")

    # ==========================================
    # 7. QUOTAS (Optional)
    # ==========================================
    if args.quotas:
        print("\n" + "="*80)
        print(" VAST CLUSTER QUOTAS")
        print("="*80)
        try:
            quotas = client.quotas.get()
            if quotas:
                for quota in quotas:
                    q_id = quota.get('id', 'N/A')
                    q_path = quota.get('path', 'N/A')
                    q_limit = quota.get('hard_limit', 'No Limit')
                    print(f"ID: {q_id:<6} | Path: {q_path:<50} | Hard Limit: {q_limit}")
            else:
                print("No quotas found.")
        except Exception as e:
            print(f"⚠️ Could not fetch Quotas: {e}")

    # ==========================================
    # 8. VIEWS (Optional)
    # ==========================================
    if args.views:
        print("\n" + "="*80)
        print(" VAST CLUSTER VIEWS (VOLUMES)")
        print("="*80)
        try:
            views = client.views.get()
            if views:
                for view in views:
                    v_id = view.get('id', 'N/A')
                    v_name = view.get('name', 'N/A')
                    v_path = view.get('path', 'N/A')
                    print(f"ID: {v_id:<7} | Name: {v_name:<45} | Path: {v_path}")
            else:
                print("No views found.")
        except Exception as e:
            print(f"⚠️ Could not fetch Views: {e}")

if __name__ == "__main__":
    list_cluster_resources()