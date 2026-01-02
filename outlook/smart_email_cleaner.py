"""
Smart Outlook Email Cleaner
============================
Automatically identifies and cleans up:
- Marketing/promotional emails
- Newsletters you never open
- Old unread emails
- Spam patterns
- Subscriptions you consistently ignore

SETUP:
1. pip install msal requests
2. python smart_email_cleaner.py
"""

import msal
import requests
import webbrowser
from collections import defaultdict
from datetime import datetime, timedelta
import re
import time

# Auth settings
CLIENT_ID = "9e5f94bc-e8a4-4e73-b8be-63364c29d753"
AUTHORITY = "https://login.microsoftonline.com/consumers"
SCOPES = ["https://graph.microsoft.com/Mail.Read", 
          "https://graph.microsoft.com/Mail.ReadWrite"]
GRAPH_ENDPOINT = "https://graph.microsoft.com/v1.0"

# Marketing/spam indicators
MARKETING_KEYWORDS = [
    'unsubscribe', 'opt-out', 'opt out', 'email preferences', 'manage preferences',
    'view in browser', 'view online', 'click here', 'limited time', 'act now',
    'don\'t miss', 'exclusive offer', 'special offer', 'discount', 'sale',
    'free shipping', 'order now', 'buy now', 'shop now', 'deal', 'promo',
    'newsletter', 'weekly digest', 'daily digest', 'notification settings',
    'update your preferences', 'manage subscriptions', 'email settings'
]

MARKETING_SENDER_PATTERNS = [
    'noreply', 'no-reply', 'newsletter', 'marketing', 'promo', 'offers',
    'deals', 'news@', 'info@', 'hello@', 'support@', 'team@', 'updates@',
    'notifications@', 'alert@', 'mailer', 'campaign', 'bulk', 'mass'
]

KNOWN_MARKETING_DOMAINS = [
    'linkedin.com', 'facebookmail.com', 'twitter.com', 'pinterest.com',
    'quora.com', 'medium.com', 'substack.com', 'mailchimp.com', 
    'sendgrid.net', 'amazonses.com', 'constantcontact.com',
    'hubspot.com', 'salesforce.com', 'marketo.com', 'pardot.com',
    'groupon.com', 'retailmenot.com', 'slickdeals.net',
    'wish.com', 'aliexpress.com', 'banggood.com', 'shein.com',
    'spotify.com', 'netflix.com', 'hulu.com', 'discord.com',
    'uber.com', 'lyft.com', 'doordash.com', 'grubhub.com',
    'yelp.com', 'tripadvisor.com', 'booking.com', 'expedia.com'
]


def authenticate():
    """Authenticate using device code flow."""
    app = msal.PublicClientApplication(CLIENT_ID, authority=AUTHORITY)
    
    accounts = app.get_accounts()
    if accounts:
        result = app.acquire_token_silent(SCOPES, account=accounts[0])
        if result and "access_token" in result:
            print("✓ Using cached login")
            return result["access_token"]
    
    flow = app.initiate_device_flow(scopes=SCOPES)
    
    if "user_code" not in flow:
        print(f"Error: {flow.get('error_description', 'Failed to start login')}")
        return None
    
    print("\n" + "="*60)
    print("SIGN IN TO MICROSOFT")
    print("="*60)
    print(f"\n1. Go to: {flow['verification_uri']}")
    print(f"2. Enter code: {flow['user_code']}")
    print("\nOpening browser...")
    print("="*60)
    
    webbrowser.open(flow["verification_uri"])
    
    print("\nWaiting for you to sign in...")
    
    result = app.acquire_token_by_device_flow(flow)
    
    if "access_token" in result:
        print("\n✓ Signed in successfully!")
        return result["access_token"]
    else:
        print(f"\n✗ Sign in failed: {result.get('error_description', 'Unknown error')}")
        return None


def get_headers(token):
    return {"Authorization": f"Bearer {token}"}


def fetch_all_emails(token, max_emails=5000, include_read=True):
    """Fetch emails from inbox."""
    headers = get_headers(token)
    emails = []
    
    url = f"{GRAPH_ENDPOINT}/me/mailFolders/inbox/messages"
    params = {
        "$select": "id,subject,from,receivedDateTime,isRead,bodyPreview",
        "$orderby": "receivedDateTime desc",
        "$top": 100
    }
    
    print(f"\nFetching emails (up to {max_emails})...")
    start_time = time.time()
    
    while url and len(emails) < max_emails:
        try:
            response = requests.get(url, headers=headers, params=params, timeout=30)
            
            if response.status_code == 429:  # Rate limited
                print("  Rate limited, waiting 30 seconds...")
                time.sleep(30)
                continue
            
            if response.status_code != 200:
                print(f"  Error {response.status_code}")
                break
            
            data = response.json()
            batch = data.get("value", [])
            emails.extend(batch)
            
            url = data.get("@odata.nextLink")
            params = None
            
            if len(emails) % 500 == 0:
                elapsed = time.time() - start_time
                print(f"  {len(emails)} emails fetched... ({elapsed:.0f}s)")
                
        except Exception as e:
            print(f"  Error: {e}")
            time.sleep(5)
            continue
    
    elapsed = time.time() - start_time
    print(f"✓ Fetched {len(emails)} emails in {elapsed:.0f} seconds")
    return emails


def is_marketing_email(email):
    """Check if email appears to be marketing/promotional."""
    subject = (email.get("subject") or "").lower()
    body_preview = (email.get("bodyPreview") or "").lower()
    sender_email = email.get("from", {}).get("emailAddress", {}).get("address", "").lower()
    sender_name = email.get("from", {}).get("emailAddress", {}).get("name", "").lower()
    
    score = 0
    reasons = []
    
    # Check sender patterns
    for pattern in MARKETING_SENDER_PATTERNS:
        if pattern in sender_email or pattern in sender_name:
            score += 2
            reasons.append(f"sender pattern: {pattern}")
            break
    
    # Check known marketing domains
    for domain in KNOWN_MARKETING_DOMAINS:
        if domain in sender_email:
            score += 3
            reasons.append(f"known marketing domain: {domain}")
            break
    
    # Check for marketing keywords in subject/body
    text = subject + " " + body_preview
    keyword_matches = 0
    for keyword in MARKETING_KEYWORDS:
        if keyword in text:
            keyword_matches += 1
    
    if keyword_matches >= 3:
        score += 4
        reasons.append(f"{keyword_matches} marketing keywords")
    elif keyword_matches >= 1:
        score += 2
        reasons.append(f"{keyword_matches} marketing keyword(s)")
    
    # Check for unsubscribe (strong indicator)
    if 'unsubscribe' in text:
        score += 3
        reasons.append("contains 'unsubscribe'")
    
    return score >= 3, score, reasons


def analyze_emails(emails):
    """Analyze all emails and categorize them."""
    print("\nAnalyzing emails...")
    
    sender_stats = defaultdict(lambda: {
        "total": 0,
        "unread": 0,
        "read": 0,
        "marketing_score": 0,
        "emails": [],
        "name": "",
        "oldest": None,
        "newest": None,
        "read_rate": 0
    })
    
    now = datetime.utcnow()
    
    for email in emails:
        sender = email.get("from", {}).get("emailAddress", {})
        addr = sender.get("address", "unknown").lower()
        name = sender.get("name", addr)
        is_read = email.get("isRead", False)
        received = email.get("receivedDateTime", "")
        
        # Check if marketing
        is_marketing, marketing_score, _ = is_marketing_email(email)
        
        stats = sender_stats[addr]
        stats["total"] += 1
        stats["name"] = name
        stats["emails"].append(email)
        stats["marketing_score"] = max(stats["marketing_score"], marketing_score)
        
        if is_read:
            stats["read"] += 1
        else:
            stats["unread"] += 1
        
        # Track dates
        if received:
            if not stats["oldest"] or received < stats["oldest"]:
                stats["oldest"] = received
            if not stats["newest"] or received > stats["newest"]:
                stats["newest"] = received
    
    # Calculate read rates
    for addr, stats in sender_stats.items():
        if stats["total"] > 0:
            stats["read_rate"] = stats["read"] / stats["total"]
    
    return sender_stats


def categorize_senders(sender_stats):
    """Categorize senders into cleanup groups."""
    
    categories = {
        "marketing": {
            "title": "📢 MARKETING & PROMOTIONAL",
            "description": "Emails identified as marketing/promotional",
            "senders": [],
            "email_count": 0
        },
        "never_opened": {
            "title": "🚫 NEVER OPENED (5+ emails)",
            "description": "Senders with 5+ emails you've never opened",
            "senders": [],
            "email_count": 0
        },
        "rarely_opened": {
            "title": "😴 RARELY OPENED (<20% read rate, 3+ emails)",
            "description": "Senders you almost never read",
            "senders": [],
            "email_count": 0
        },
        "old_unread": {
            "title": "📆 OLD UNREAD (30+ days)",
            "description": "Unread emails older than 30 days",
            "senders": [],
            "email_count": 0
        },
        "bulk_senders": {
            "title": "📬 BULK SENDERS (20+ emails)",
            "description": "Senders flooding your inbox",
            "senders": [],
            "email_count": 0
        }
    }
    
    now = datetime.utcnow()
    thirty_days_ago = now - timedelta(days=30)
    
    for addr, stats in sender_stats.items():
        # Marketing emails
        if stats["marketing_score"] >= 3:
            categories["marketing"]["senders"].append((addr, stats))
            categories["marketing"]["email_count"] += stats["total"]
        
        # Never opened (5+ emails, 0% read rate)
        if stats["total"] >= 5 and stats["read"] == 0:
            categories["never_opened"]["senders"].append((addr, stats))
            categories["never_opened"]["email_count"] += stats["total"]
        
        # Rarely opened (<20% read rate, 3+ emails)
        elif stats["total"] >= 3 and stats["read_rate"] < 0.2 and stats["read_rate"] > 0:
            categories["rarely_opened"]["senders"].append((addr, stats))
            categories["rarely_opened"]["email_count"] += stats["total"]
        
        # Bulk senders (20+ emails)
        if stats["total"] >= 20:
            categories["bulk_senders"]["senders"].append((addr, stats))
            categories["bulk_senders"]["email_count"] += stats["total"]
        
        # Old unread emails
        old_unread_emails = []
        for email in stats["emails"]:
            if not email.get("isRead"):
                received = email.get("receivedDateTime", "")
                if received:
                    try:
                        received_date = datetime.fromisoformat(received.replace("Z", "+00:00"))
                        if received_date.replace(tzinfo=None) < thirty_days_ago:
                            old_unread_emails.append(email)
                    except:
                        pass
        
        if old_unread_emails:
            old_stats = stats.copy()
            old_stats["emails"] = old_unread_emails
            old_stats["total"] = len(old_unread_emails)
            categories["old_unread"]["senders"].append((addr, old_stats))
            categories["old_unread"]["email_count"] += len(old_unread_emails)
    
    # Sort each category by email count
    for cat in categories.values():
        cat["senders"].sort(key=lambda x: x[1]["total"], reverse=True)
    
    return categories


def display_category(category, show_limit=15):
    """Display a category of senders."""
    print(f"\n{'='*70}")
    print(f"{category['title']}")
    print(f"{category['description']}")
    print(f"Total: {category['email_count']} emails from {len(category['senders'])} senders")
    print('='*70)
    
    if not category["senders"]:
        print("  (none found)")
        return []
    
    displayed = []
    for i, (addr, stats) in enumerate(category["senders"][:show_limit]):
        displayed.append((addr, stats))
        read_pct = stats["read_rate"] * 100
        print(f"\n  {i+1}. {stats['name']}")
        print(f"     {addr}")
        print(f"     {stats['total']} emails | {stats['unread']} unread | {read_pct:.0f}% read rate")
    
    if len(category["senders"]) > show_limit:
        print(f"\n  ... and {len(category['senders']) - show_limit} more senders")
    
    return displayed


def delete_emails_batch(token, emails, to_trash=True):
    """Delete a batch of emails."""
    headers = get_headers(token)
    headers["Content-Type"] = "application/json"
    
    success = 0
    failed = 0
    
    for i, email in enumerate(emails):
        eid = email["id"]
        
        try:
            if to_trash:
                url = f"{GRAPH_ENDPOINT}/me/messages/{eid}/move"
                r = requests.post(url, headers=headers, json={"destinationId": "deleteditems"}, timeout=10)
                ok = r.status_code == 201
            else:
                url = f"{GRAPH_ENDPOINT}/me/messages/{eid}"
                r = requests.delete(url, headers=headers, timeout=10)
                ok = r.status_code == 204
            
            if ok:
                success += 1
            else:
                failed += 1
                
            # Progress update
            if (i + 1) % 50 == 0:
                print(f"    Progress: {i+1}/{len(emails)} ({success} success, {failed} failed)")
                
            # Rate limiting
            if (i + 1) % 100 == 0:
                time.sleep(1)
                
        except Exception as e:
            failed += 1
    
    return success, failed


def cleanup_category(token, category, sender_stats):
    """Clean up all emails in a category."""
    all_emails = []
    
    for addr, stats in category["senders"]:
        all_emails.extend(stats["emails"])
    
    if not all_emails:
        print("No emails to clean up.")
        return 0
    
    print(f"\nThis will move {len(all_emails)} emails to trash.")
    confirm = input("Continue? (yes/no): ").strip().lower()
    
    if confirm != 'yes':
        print("Cancelled.")
        return 0
    
    print(f"\nMoving {len(all_emails)} emails to trash...")
    success, failed = delete_emails_batch(token, all_emails, to_trash=True)
    print(f"\n✓ Done: {success} moved to trash, {failed} failed")
    return success


def cleanup_selected_senders(token, senders_list):
    """Clean up emails from selected senders."""
    all_emails = []
    
    for addr, stats in senders_list:
        all_emails.extend(stats["emails"])
    
    if not all_emails:
        print("No emails to clean up.")
        return 0
    
    print(f"\nThis will move {len(all_emails)} emails to trash.")
    confirm = input("Continue? (yes/no): ").strip().lower()
    
    if confirm != 'yes':
        print("Cancelled.")
        return 0
    
    print(f"\nMoving {len(all_emails)} emails to trash...")
    success, failed = delete_emails_batch(token, all_emails, to_trash=True)
    print(f"\n✓ Done: {success} moved to trash, {failed} failed")
    return success


def interactive_menu(token, categories, sender_stats):
    """Interactive menu for cleanup."""
    
    while True:
        print("\n" + "="*70)
        print("SMART EMAIL CLEANER - MAIN MENU")
        print("="*70)
        print("\nCategories found:\n")
        
        menu_items = []
        for key, cat in categories.items():
            if cat["senders"]:
                menu_items.append((key, cat))
                print(f"  {len(menu_items)}. {cat['title']}")
                print(f"     {cat['email_count']} emails from {len(cat['senders'])} senders\n")
        
        print(f"  A. Auto-clean ALL categories (move to trash)")
        print(f"  S. Show inbox statistics")
        print(f"  Q. Quit\n")
        
        choice = input("Select option: ").strip().lower()
        
        if choice == 'q':
            print("\nGoodbye!")
            break
        
        elif choice == 's':
            # Show statistics
            total_emails = sum(s["total"] for s in sender_stats.values())
            total_unread = sum(s["unread"] for s in sender_stats.values())
            total_senders = len(sender_stats)
            
            print(f"\n📊 INBOX STATISTICS")
            print(f"   Total emails analyzed: {total_emails}")
            print(f"   Total unread: {total_unread}")
            print(f"   Unique senders: {total_senders}")
            print(f"\n   Top 10 senders by volume:")
            
            top_senders = sorted(sender_stats.items(), key=lambda x: x[1]["total"], reverse=True)[:10]
            for i, (addr, stats) in enumerate(top_senders):
                print(f"   {i+1}. {stats['name'][:30]} - {stats['total']} emails")
        
        elif choice == 'a':
            # Auto-clean all
            total_to_clean = sum(cat["email_count"] for cat in categories.values() if cat["senders"])
            print(f"\n⚠️  AUTO-CLEAN will move approximately {total_to_clean} emails to trash.")
            print("   (Some emails may appear in multiple categories, actual count may be lower)")
            
            confirm = input("\nType 'yes' to proceed: ").strip().lower()
            
            if confirm == 'yes':
                all_email_ids = set()
                all_emails = []
                
                for cat in categories.values():
                    for addr, stats in cat["senders"]:
                        for email in stats["emails"]:
                            if email["id"] not in all_email_ids:
                                all_email_ids.add(email["id"])
                                all_emails.append(email)
                
                print(f"\nMoving {len(all_emails)} unique emails to trash...")
                success, failed = delete_emails_batch(token, all_emails, to_trash=True)
                print(f"\n✓ Complete: {success} moved to trash, {failed} failed")
            else:
                print("Cancelled.")
        
        elif choice.isdigit() and 1 <= int(choice) <= len(menu_items):
            # Selected a category
            idx = int(choice) - 1
            key, cat = menu_items[idx]
            
            displayed = display_category(cat)
            
            print(f"\nOptions:")
            print(f"  1. Clean ALL {len(cat['senders'])} senders in this category")
            print(f"  2. Select specific senders to clean")
            print(f"  3. Back to main menu")
            
            sub_choice = input("\nSelect: ").strip()
            
            if sub_choice == '1':
                cleanup_category(token, cat, sender_stats)
            
            elif sub_choice == '2':
                print("\nEnter sender numbers (e.g., 1,3,5 or 1-5 or 'all'):")
                sel = input("Selection: ").strip().lower()
                
                selected = []
                
                if sel == 'all':
                    selected = displayed
                elif '-' in sel and ',' not in sel:
                    try:
                        a, b = map(int, sel.split('-'))
                        selected = displayed[a-1:b]
                    except:
                        print("Invalid range")
                else:
                    try:
                        nums = [int(x.strip()) for x in sel.split(',')]
                        selected = [displayed[n-1] for n in nums if 0 < n <= len(displayed)]
                    except:
                        print("Invalid selection")
                
                if selected:
                    cleanup_selected_senders(token, selected)
        
        else:
            print("Invalid option")


def main():
    print("""
╔══════════════════════════════════════════════════════════════════════════╗
║                    SMART OUTLOOK EMAIL CLEANER                           ║
║         Automatically finds and cleans marketing, spam, and              ║
║         subscriptions you never read                                     ║
╚══════════════════════════════════════════════════════════════════════════╝
    """)
    
    # Authenticate
    token = authenticate()
    if not token:
        input("\nPress Enter to exit...")
        return
    
    # Fetch emails
    print("\nHow many emails to analyze?")
    print("  1. Quick scan (1,000 emails)")
    print("  2. Normal scan (5,000 emails)")
    print("  3. Deep scan (10,000 emails)")
    print("  4. Full scan (all emails - may take a while)")
    
    scan_choice = input("\nChoice (1-4): ").strip()
    
    max_emails = {
        "1": 1000,
        "2": 5000,
        "3": 10000,
        "4": 50000
    }.get(scan_choice, 5000)
    
    emails = fetch_all_emails(token, max_emails=max_emails)
    
    if not emails:
        print("\nNo emails found!")
        input("\nPress Enter to exit...")
        return
    
    # Analyze
    sender_stats = analyze_emails(emails)
    
    # Categorize
    categories = categorize_senders(sender_stats)
    
    # Show summary
    print("\n" + "="*70)
    print("📊 ANALYSIS COMPLETE")
    print("="*70)
    
    total_cleanable = 0
    for key, cat in categories.items():
        if cat["senders"]:
            print(f"\n  {cat['title']}")
            print(f"    {cat['email_count']} emails from {len(cat['senders'])} senders")
            total_cleanable += cat["email_count"]
    
    print(f"\n  💡 Potential cleanup: ~{total_cleanable} emails")
    print("     (some may overlap between categories)")
    
    # Interactive menu
    interactive_menu(token, categories, sender_stats)
    
    input("\nPress Enter to exit...")


if __name__ == "__main__":
    main()
