"""
Smart Gmail Cleaner
====================
Automatically identifies and cleans up:
- Marketing/promotional emails
- Newsletters you never open
- Old unread emails
- Spam patterns
- Subscriptions you consistently ignore

SETUP:
1. pip install google-auth-oauthlib google-api-python-client

2. Create Google Cloud credentials (one-time, ~5 minutes):
   a. Go to https://console.cloud.google.com/
   b. Create a new project (or select existing)
   c. Go to "APIs & Services" > "Enable APIs" > Enable "Gmail API"
   d. Go to "APIs & Services" > "Credentials"
   e. Click "Create Credentials" > "OAuth client ID"
   f. Select "Desktop app" and give it a name
   g. Download the JSON file
   h. Rename it to "credentials.json" and put it in the same folder as this script

3. Run: python smart_gmail_cleaner.py
"""

import os
import pickle
import re
import time
from datetime import datetime, timedelta
from collections import defaultdict
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import base64

# Gmail API scopes
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

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
    'yelp.com', 'tripadvisor.com', 'booking.com', 'expedia.com',
    'youtube.com', 'tiktok.com', 'instagram.com', 'snapchat.com'
]


def authenticate():
    """Authenticate with Gmail API."""
    creds = None
    
    # Check for cached credentials
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    
    # If no valid credentials, authenticate
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Refreshing credentials...")
            creds.refresh(Request())
        else:
            if not os.path.exists('credentials.json'):
                print("\n" + "="*60)
                print("ERROR: credentials.json not found!")
                print("="*60)
                print("\nYou need to set up Google Cloud credentials first.")
                print("\nQuick setup:")
                print("1. Go to https://console.cloud.google.com/")
                print("2. Create a project")
                print("3. Enable Gmail API")
                print("4. Create OAuth credentials (Desktop app)")
                print("5. Download and rename to 'credentials.json'")
                print("6. Place in same folder as this script")
                print("\nSee full instructions at top of this script.")
                return None
            
            print("\nOpening browser for Google sign-in...")
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save credentials for next time
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    
    print("✓ Authenticated with Gmail")
    return build('gmail', 'v1', credentials=creds)


def get_email_header(headers, name):
    """Extract a specific header value."""
    for header in headers:
        if header['name'].lower() == name.lower():
            return header['value']
    return ""


def parse_sender(from_header):
    """Parse sender email and name from From header."""
    if not from_header:
        return "unknown", "unknown"
    
    match = re.search(r'<([^>]+)>', from_header)
    if match:
        email = match.group(1).lower()
        name = from_header.replace(f'<{match.group(1)}>', '').strip().strip('"')
        return email, name if name else email
    
    if '@' in from_header:
        return from_header.lower().strip(), from_header.lower().strip()
    
    return from_header, from_header


def fetch_emails(service, max_emails=5000, query=""):
    """Fetch emails from Gmail."""
    emails = []
    page_token = None
    
    print(f"\nFetching emails{' matching: ' + query if query else ''}...")
    start_time = time.time()
    
    while len(emails) < max_emails:
        try:
            results = service.users().messages().list(
                userId='me',
                maxResults=min(500, max_emails - len(emails)),
                pageToken=page_token,
                q=query if query else None
            ).execute()
            
            messages = results.get('messages', [])
            
            if not messages:
                break
            
            # Fetch details for each message
            for msg in messages:
                try:
                    msg_data = service.users().messages().get(
                        userId='me',
                        id=msg['id'],
                        format='metadata',
                        metadataHeaders=['From', 'Subject', 'Date']
                    ).execute()
                    
                    headers = msg_data.get('payload', {}).get('headers', [])
                    
                    emails.append({
                        'id': msg['id'],
                        'threadId': msg.get('threadId'),
                        'from': get_email_header(headers, 'From'),
                        'subject': get_email_header(headers, 'Subject'),
                        'date': get_email_header(headers, 'Date'),
                        'snippet': msg_data.get('snippet', ''),
                        'labelIds': msg_data.get('labelIds', []),
                        'isRead': 'UNREAD' not in msg_data.get('labelIds', [])
                    })
                    
                except Exception as e:
                    continue
                
                if len(emails) % 200 == 0:
                    elapsed = time.time() - start_time
                    print(f"  {len(emails)} emails fetched... ({elapsed:.0f}s)")
            
            page_token = results.get('nextPageToken')
            if not page_token:
                break
                
            # Small delay to avoid rate limiting
            time.sleep(0.1)
            
        except Exception as e:
            print(f"  Error: {e}")
            break
    
    elapsed = time.time() - start_time
    print(f"✓ Fetched {len(emails)} emails in {elapsed:.0f} seconds")
    return emails


def is_marketing_email(email):
    """Check if email appears to be marketing/promotional."""
    subject = (email.get("subject") or "").lower()
    snippet = (email.get("snippet") or "").lower()
    sender_email, sender_name = parse_sender(email.get("from", ""))
    sender_name = sender_name.lower()
    
    # Check if Gmail already categorized it as promotional
    labels = email.get('labelIds', [])
    if 'CATEGORY_PROMOTIONS' in labels:
        return True, 5, ["Gmail marked as Promotions"]
    
    if 'CATEGORY_SOCIAL' in labels:
        return True, 4, ["Gmail marked as Social"]
    
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
    
    # Check for marketing keywords
    text = subject + " " + snippet
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
    
    # Check for unsubscribe
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
        "read_rate": 0,
        "is_promotional": False
    })
    
    for email in emails:
        sender_email, sender_name = parse_sender(email.get("from", ""))
        is_read = email.get("isRead", False)
        
        # Check if marketing
        is_marketing, marketing_score, _ = is_marketing_email(email)
        
        stats = sender_stats[sender_email]
        stats["total"] += 1
        stats["name"] = sender_name
        stats["emails"].append(email)
        stats["marketing_score"] = max(stats["marketing_score"], marketing_score)
        
        if 'CATEGORY_PROMOTIONS' in email.get('labelIds', []):
            stats["is_promotional"] = True
        
        if is_read:
            stats["read"] += 1
        else:
            stats["unread"] += 1
        
        # Track dates
        date_str = email.get("date", "")
        if date_str:
            if not stats["oldest"] or date_str < stats["oldest"]:
                stats["oldest"] = date_str
            if not stats["newest"] or date_str > stats["newest"]:
                stats["newest"] = date_str
    
    # Calculate read rates
    for addr, stats in sender_stats.items():
        if stats["total"] > 0:
            stats["read_rate"] = stats["read"] / stats["total"]
    
    return sender_stats


def categorize_senders(sender_stats):
    """Categorize senders into cleanup groups."""
    
    categories = {
        "promotional": {
            "title": "📢 PROMOTIONS (Gmail category)",
            "description": "Emails Gmail identified as promotional",
            "senders": [],
            "email_count": 0
        },
        "marketing": {
            "title": "📧 MARKETING & NEWSLETTERS",
            "description": "Emails with marketing patterns (unsubscribe links, etc.)",
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
        # Gmail Promotions category
        if stats["is_promotional"]:
            categories["promotional"]["senders"].append((addr, stats))
            categories["promotional"]["email_count"] += stats["total"]
        
        # Marketing emails (by our detection)
        elif stats["marketing_score"] >= 3:
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
                # Check if older than 30 days
                date_str = email.get("date", "")
                if date_str:
                    try:
                        # Parse various date formats
                        for fmt in ["%a, %d %b %Y %H:%M:%S %z", "%d %b %Y %H:%M:%S %z"]:
                            try:
                                email_date = datetime.strptime(date_str[:31], fmt)
                                if email_date.replace(tzinfo=None) < thirty_days_ago:
                                    old_unread_emails.append(email)
                                break
                            except:
                                continue
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


def delete_emails_batch(service, emails, to_trash=True):
    """Delete a batch of emails."""
    success = 0
    failed = 0
    
    for i, email in enumerate(emails):
        try:
            if to_trash:
                service.users().messages().trash(userId='me', id=email['id']).execute()
            else:
                service.users().messages().delete(userId='me', id=email['id']).execute()
            
            success += 1
            
            if (i + 1) % 50 == 0:
                print(f"    Progress: {i+1}/{len(emails)} ({success} success, {failed} failed)")
            
            # Rate limiting
            if (i + 1) % 100 == 0:
                time.sleep(1)
                
        except Exception as e:
            failed += 1
    
    return success, failed


def cleanup_category(service, category):
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
    success, failed = delete_emails_batch(service, all_emails, to_trash=True)
    print(f"\n✓ Done: {success} moved to trash, {failed} failed")
    return success


def cleanup_selected_senders(service, senders_list):
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
    success, failed = delete_emails_batch(service, all_emails, to_trash=True)
    print(f"\n✓ Done: {success} moved to trash, {failed} failed")
    return success


def interactive_menu(service, categories, sender_stats):
    """Interactive menu for cleanup."""
    
    while True:
        print("\n" + "="*70)
        print("SMART GMAIL CLEANER - MAIN MENU")
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
            total_to_clean = sum(cat["email_count"] for cat in categories.values() if cat["senders"])
            print(f"\n⚠️  AUTO-CLEAN will move approximately {total_to_clean} emails to trash.")
            print("   (Some emails may appear in multiple categories)")
            
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
                success, failed = delete_emails_batch(service, all_emails, to_trash=True)
                print(f"\n✓ Complete: {success} moved to trash, {failed} failed")
            else:
                print("Cancelled.")
        
        elif choice.isdigit() and 1 <= int(choice) <= len(menu_items):
            idx = int(choice) - 1
            key, cat = menu_items[idx]
            
            displayed = display_category(cat)
            
            print(f"\nOptions:")
            print(f"  1. Clean ALL {len(cat['senders'])} senders in this category")
            print(f"  2. Select specific senders to clean")
            print(f"  3. Back to main menu")
            
            sub_choice = input("\nSelect: ").strip()
            
            if sub_choice == '1':
                cleanup_category(service, cat)
            
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
                    cleanup_selected_senders(service, selected)
        
        else:
            print("Invalid option")


def main():
    print("""
╔══════════════════════════════════════════════════════════════════════════╗
║                      SMART GMAIL CLEANER                                 ║
║         Automatically finds and cleans marketing, spam, and              ║
║         subscriptions you never read                                     ║
╚══════════════════════════════════════════════════════════════════════════╝
    """)
    
    # Authenticate
    service = authenticate()
    if not service:
        input("\nPress Enter to exit...")
        return
    
    # Fetch emails
    print("\nHow many emails to analyze?")
    print("  1. Quick scan (1,000 emails)")
    print("  2. Normal scan (5,000 emails)")
    print("  3. Deep scan (10,000 emails)")
    print("  4. Full scan (25,000 emails - takes a while)")
    
    scan_choice = input("\nChoice (1-4): ").strip()
    
    max_emails = {
        "1": 1000,
        "2": 5000,
        "3": 10000,
        "4": 25000
    }.get(scan_choice, 5000)
    
    emails = fetch_emails(service, max_emails=max_emails)
    
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
    interactive_menu(service, categories, sender_stats)
    
    input("\nPress Enter to exit...")


if __name__ == "__main__":
    main()
