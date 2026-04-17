import requests
from bs4 import BeautifulSoup
import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import time

# Configuration
BASELINE_SALARY = 65000
EMAIL_SENDER = os.getenv('EMAIL_SENDER')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')
EMAIL_RECEIVER = os.getenv('EMAIL_RECEIVER')

# Known Government Salary Code Mapping (2025/2026 approx basic)
SALARY_CODES = {
    'MA 4': 64320,
    'MM 1-1': 91690,
    'MA 2-2': 50540,
    'MM 2-1': 105000,
    'SL 1-1': 120000,
    'SL 1': 82150,    # New 2025 Class 1
    'MN 3': 52250,    # Entry level
    'MN 5': 58660,    # Mid level
    'SL 3': 156000    # Special grade
}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
}

def extract_salary_value(text):
    """
    Extracts a numerical value from text containing 'Rs. X,XXX' or salary codes.
    """
    # 1. Search for salary codes (e.g., MM 1-1)
    for code, value in SALARY_CODES.items():
        if code in text:
            return value
            
    # 2. Search for explicit currency values (e.g., Rs. 75,000)
    match = re.search(r'Rs\.\s?([\d,]+)', text)
    if match:
        val_str = match.group(1).replace(',', '')
        return int(val_str)
        
    return 0

def scrape_governmentjob_lk():
    """
    Scrapes IT category jobs from governmentjob.lk.
    Correct URL for category uses taxonomy parameter.
    """
    url = "https://governmentjob.lk/?taxonomy=job_listing_category&term=it-jobs"
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        jobs = []
        # Site uses 'job_listing' elements or links in some structures
        # Homepage grid uses specific pattern
        for link in soup.find_all('a'):
            href = link.get('href', '')
            if 'https://governmentjob.lk/job/' in href:
                job_title = link.get_text(strip=True)
                if not job_title: continue
                
                # Navigate to job details
                try:
                    time.sleep(1) # Be nice
                    details_res = requests.get(href, headers=HEADERS, timeout=15)
                    details_soup = BeautifulSoup(details_res.text, 'html.parser')
                    content = details_soup.get_text()
                    
                    salary = extract_salary_value(content)
                    
                    if salary > BASELINE_SALARY:
                        jobs.append({
                            'title': job_title,
                            'link': href,
                            'salary': salary,
                            'source': 'governmentjob.lk'
                        })
                except Exception as e:
                    print(f"Error fetching details for {href}: {e}")
        
        return jobs
    except Exception as e:
        print(f"Error scraping governmentjob.lk: {e}")
        return []

def scrape_gazette_lk():
    """
    Scrapes IT category jobs from gazette.lk.
    Increased timeout and retry logic for stability.
    """
    # Try the most specific category URL
    url = "https://www.gazette.lk/it-jobs" 
    try:
        response = requests.get(url, headers=HEADERS, timeout=20)
        # If 404, try searching for IT
        if response.status_code == 404:
            url = "https://www.gazette.lk/?s=Information+Technology"
            response = requests.get(url, headers=HEADERS, timeout=20)
            
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        jobs = []
        # WordPress Magazine Plus theme structure
        for entry in soup.find_all('article'):
            link_tag = entry.find('a')
            if not link_tag: continue
            
            job_link = link_tag.get('href', '')
            job_title = link_tag.get_text(strip=True)
            
            if not job_title or 'https://www.gazette.lk/' not in job_link:
                continue
                
            try:
                time.sleep(1)
                details_res = requests.get(job_link, headers=HEADERS, timeout=20)
                details_soup = BeautifulSoup(details_res.text, 'html.parser')
                content = details_soup.get_text()
                
                salary = extract_salary_value(content)
                
                if salary > BASELINE_SALARY:
                    jobs.append({
                        'title': job_title,
                        'link': job_link,
                        'salary': salary,
                        'source': 'gazette.lk'
                    })
            except Exception as e:
                print(f"Error fetching details for {job_link}: {e}")
        
        return jobs
    except Exception as e:
        print(f"Error scraping gazette.lk: {e}")
        return []

def send_email(jobs):
    """
    Sends an email with the filtered high-paying job listings.
    """
    if not jobs:
        print("No high-paying jobs found today.")
        return

    if not all([EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_RECEIVER]):
        print("Missing email credentials. Skipping email notification.")
        return

    # Deduplicate jobs by link
    seen_links = set()
    unique_jobs = []
    for job in jobs:
        if job['link'] not in seen_links:
            unique_jobs.append(job)
            seen_links.add(job['link'])

    msg = MIMEMultipart()
    msg['From'] = EMAIL_SENDER
    msg['To'] = EMAIL_RECEIVER
    msg['Subject'] = f"Found {len(unique_jobs)} High-Paying Government IT Jobs (> Rs. {BASELINE_SALARY})"

    html_content = f"<h2>Found {len(unique_jobs)} jobs exceeding your baseline:</h2><ul>"
    for job in unique_jobs:
        html_content += f"""
            <li>
                <strong>{job['title']}</strong><br>
                Source: {job['source']}<br>
                Estimated Basic: Rs. {job['salary']:,}<br>
                <a href="{job['link']}">Apply Here</a>
            </li><br>
        """
    html_content += "</ul>"
    
    msg.attach(MIMEText(html_content, 'html'))

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, msg.as_string())
        print("Email notification sent successfully.")
    except Exception as e:
        print(f"Failed to send email: {e}")

if __name__ == "__main__":
    print("Starting automated job search...")
    found_jobs = []
    found_jobs.extend(scrape_governmentjob_lk())
    found_jobs.extend(scrape_gazette_lk())
    send_email(found_jobs)
