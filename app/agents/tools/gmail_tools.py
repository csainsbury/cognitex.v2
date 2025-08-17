"""
Gmail tools for email operations.
These are stateless functions that can be used by agents to interact with Gmail.
The docstrings are critical as they serve as API documentation for the LLM.
"""
import logging
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
import base64
from email.mime.text import MIMEText

from app.services.google_api_clients import google_api_client

logger = logging.getLogger(__name__)

def search_emails(user_id: str, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
    """
    Searches Gmail for emails matching the query.
    
    Args:
        user_id: The user's ID for authentication
        query: Gmail search query using standard Gmail search syntax
               Examples:
               - "is:unread" - unread emails
               - "from:boss@company.com" - emails from specific sender
               - "subject:urgent" - emails with 'urgent' in subject
               - "has:attachment" - emails with attachments
               - "after:2024/1/1" - emails after a date
               - "is:important" - important emails
        max_results: Maximum number of results to return (default 10)
    
    Returns:
        List of email summaries with id, subject, sender, date, and snippet
    """
    try:
        service = google_api_client.get_gmail_service(user_id)
        if not service:
            logger.error(f"Could not get Gmail service for user {user_id}")
            return []
        
        # Execute search
        results = service.users().messages().list(
            userId='me',
            q=query,
            maxResults=max_results
        ).execute()
        
        messages = results.get('messages', [])
        email_list = []
        
        for msg in messages:
            # Get message details
            message = service.users().messages().get(
                userId='me',
                id=msg['id'],
                format='metadata',
                metadataHeaders=['From', 'Subject', 'Date']
            ).execute()
            
            # Extract headers
            headers = {h['name']: h['value'] for h in message['payload'].get('headers', [])}
            
            email_list.append({
                'id': msg['id'],
                'subject': headers.get('Subject', 'No Subject'),
                'sender': headers.get('From', 'Unknown'),
                'date': headers.get('Date', ''),
                'snippet': message.get('snippet', ''),
                'threadId': message.get('threadId', '')
            })
        
        logger.info(f"Found {len(email_list)} emails for query: {query}")
        if email_list:
            for i, email in enumerate(email_list[:3], 1):
                logger.info(f"Email {i}: subject='{email.get('subject')}', from='{email.get('sender')[:50]}'")
        return email_list
        
    except Exception as e:
        logger.error(f"Error searching emails: {e}")
        return []

def get_email_details(user_id: str, message_id: str) -> Dict[str, Any]:
    """
    Retrieves the full body and headers of a specific email by its message ID.
    
    Args:
        user_id: The user's ID for authentication
        message_id: The Gmail message ID
    
    Returns:
        Dictionary containing:
        - id: Message ID
        - subject: Email subject
        - sender: Sender email and name
        - to: Recipients
        - date: Date sent
        - body: Full email body (plain text)
        - html_body: HTML version if available
        - attachments: List of attachment names
        - labels: Gmail labels
    """
    try:
        service = google_api_client.get_gmail_service(user_id)
        if not service:
            logger.error(f"Could not get Gmail service for user {user_id}")
            return {}
        
        # Get full message
        message = service.users().messages().get(
            userId='me',
            id=message_id,
            format='full'
        ).execute()
        
        # Extract headers
        headers = {}
        for header in message['payload'].get('headers', []):
            headers[header['name']] = header['value']
        
        # Extract body
        body = extract_body(message['payload'])
        
        # Extract attachments
        attachments = extract_attachments(message['payload'])
        
        return {
            'id': message_id,
            'subject': headers.get('Subject', 'No Subject'),
            'sender': headers.get('From', 'Unknown'),
            'to': headers.get('To', ''),
            'cc': headers.get('Cc', ''),
            'date': headers.get('Date', ''),
            'body': body.get('plain', ''),
            'html_body': body.get('html', ''),
            'attachments': attachments,
            'labels': message.get('labelIds', []),
            'threadId': message.get('threadId', '')
        }
        
    except Exception as e:
        logger.error(f"Error getting email details for {message_id}: {e}")
        return {}

def get_recent_important_emails(user_id: str, hours: int = 24) -> List[Dict[str, Any]]:
    """
    Gets recent important or urgent emails from the last N hours.
    
    Args:
        user_id: The user's ID for authentication
        hours: Number of hours to look back (default 24)
    
    Returns:
        List of important/urgent emails with details
    """
    # Calculate date for query
    after_date = (datetime.now() - timedelta(hours=hours)).strftime('%Y/%m/%d')
    
    # Search for important and urgent emails
    query = f"(is:important OR subject:urgent OR subject:ASAP OR priority:high) after:{after_date}"
    
    return search_emails(user_id, query, max_results=20)

def get_unread_from_contacts(user_id: str, contacts: List[str]) -> List[Dict[str, Any]]:
    """
    Gets unread emails from specific contacts.
    
    Args:
        user_id: The user's ID for authentication
        contacts: List of email addresses or names to search for
    
    Returns:
        List of unread emails from specified contacts
    """
    if not contacts:
        return []
    
    # Build query for multiple contacts
    from_queries = [f"from:{contact}" for contact in contacts]
    query = f"is:unread ({' OR '.join(from_queries)})"
    
    return search_emails(user_id, query, max_results=50)

def mark_as_read(user_id: str, message_ids: List[str]) -> bool:
    """
    Marks emails as read.
    
    Args:
        user_id: The user's ID for authentication
        message_ids: List of Gmail message IDs to mark as read
    
    Returns:
        True if successful, False otherwise
    """
    try:
        service = google_api_client.get_gmail_service(user_id)
        if not service:
            return False
        
        # Remove UNREAD label
        for message_id in message_ids:
            service.users().messages().modify(
                userId='me',
                id=message_id,
                body={'removeLabelIds': ['UNREAD']}
            ).execute()
        
        logger.info(f"Marked {len(message_ids)} messages as read")
        return True
        
    except Exception as e:
        logger.error(f"Error marking messages as read: {e}")
        return False

def extract_body(payload: Dict) -> Dict[str, str]:
    """
    Extracts email body from payload.
    
    Args:
        payload: Gmail message payload
    
    Returns:
        Dictionary with 'plain' and 'html' body content
    """
    body = {'plain': '', 'html': ''}
    
    def extract_parts(parts):
        for part in parts:
            mime_type = part.get('mimeType', '')
            
            if mime_type == 'text/plain':
                data = part['body'].get('data', '')
                if data:
                    body['plain'] += base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
            
            elif mime_type == 'text/html':
                data = part['body'].get('data', '')
                if data:
                    body['html'] += base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
            
            elif 'parts' in part:
                extract_parts(part['parts'])
    
    if 'parts' in payload:
        extract_parts(payload['parts'])
    else:
        # Single part message
        mime_type = payload.get('mimeType', '')
        data = payload.get('body', {}).get('data', '')
        
        if data:
            decoded = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
            if mime_type == 'text/plain':
                body['plain'] = decoded
            elif mime_type == 'text/html':
                body['html'] = decoded
    
    return body

def extract_attachments(payload: Dict) -> List[str]:
    """
    Extracts attachment names from payload.
    
    Args:
        payload: Gmail message payload
    
    Returns:
        List of attachment filenames
    """
    attachments = []
    
    def extract_parts(parts):
        for part in parts:
            filename = part.get('filename', '')
            if filename:
                attachments.append(filename)
            
            if 'parts' in part:
                extract_parts(part['parts'])
    
    if 'parts' in payload:
        extract_parts(payload['parts'])
    
    return attachments

def get_emails_since(user_id: str, since: datetime, max_results: int = 50) -> List[Dict[str, Any]]:
    """
    Gets all emails since a specific timestamp, without keyword filtering.
    This is used for intelligent synthesis to analyze ALL recent activity.
    
    Args:
        user_id: The user's ID for authentication
        since: Datetime to fetch emails after
        max_results: Maximum number of results (default 50)
    
    Returns:
        List of emails with full details for analysis
    """
    try:
        service = google_api_client.get_gmail_service(user_id)
        if not service:
            logger.error(f"Could not get Gmail service for user {user_id}")
            return []
        
        # Format date for Gmail query
        after_date = since.strftime('%Y/%m/%d')
        query = f"after:{after_date}"
        
        logger.info(f"Fetching all emails since {after_date} for comprehensive analysis")
        
        # Execute search
        results = service.users().messages().list(
            userId='me',
            q=query,
            maxResults=max_results
        ).execute()
        
        messages = results.get('messages', [])
        email_list = []
        
        for msg in messages:
            # Get full message details including body
            message = service.users().messages().get(
                userId='me',
                id=msg['id'],
                format='full'
            ).execute()
            
            # Extract headers
            headers = {}
            for header in message['payload'].get('headers', []):
                headers[header['name']] = header['value']
            
            # Extract body
            body = extract_body(message['payload'])
            
            # Extract attachments
            attachments = extract_attachments(message['payload'])
            
            email_list.append({
                'id': msg['id'],
                'subject': headers.get('Subject', 'No Subject'),
                'sender': headers.get('From', 'Unknown'),
                'to': headers.get('To', ''),
                'date': headers.get('Date', ''),
                'body': body.get('plain', '')[:1000],  # Limit body to 1000 chars for initial processing
                'full_body': body.get('plain', ''),  # Keep full body available
                'has_attachments': len(attachments) > 0,
                'attachment_names': attachments,
                'labels': message.get('labelIds', []),
                'threadId': message.get('threadId', ''),
                'snippet': message.get('snippet', '')
            })
        
        logger.info(f"Retrieved {len(email_list)} emails for comprehensive analysis")
        return email_list
        
    except Exception as e:
        logger.error(f"Error fetching emails since {since}: {e}")
        return []