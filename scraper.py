import requests
from bs4 import BeautifulSoup
import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

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
    """
    url = "https://governmentjob.lk/category/it-jobs/"
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        jobs = []
        for entry in soup.find_all('article'):
            title_tag = entry.find('h2')
            link_tag = entry.find('a')
            
            if not title_tag or not link_tag:
                continue
                
            job_title = title_tag.get_text(strip=True)
            job_link = link_tag['href']
            
            details_res = requests.get(job_link, headers=headers, timeout=10)
            details_soup = BeautifulSoup(details_res.text, 'html.parser')
            content = details_soup.get_text()
            
            salary = extract_salary_value(content)
            
            if salary > BASELINE_SALARY:
                jobs.append({
                    'title': job_title,
                    'link': job_link,
                    'salary': salary,
                    'source': 'governmentjob.lk'
                })
        
        return jobs
    except Exception as e:
        print(f"Error scraping governmentjob.lk: {e}")
        return []

def scrape_gazette_lk():
    """
    Scrapes IT category jobs from gazette.lk.
    """
    url = "https://www.gazette.lk/category/it-jobs/"
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        jobs = []
        # gazette.lk uses different structure, common pattern for WP themes
        for entry in soup.find_all('div', class_='listing-content'):
            title_tag = entry.find('h3')
            link_tag = entry.find('a')
            
            if not title_tag or not link_tag:
                continue
                
            job_title = title_tag.get_text(strip=True)
            job_link = link_tag['href']
            
            details_res = requests.get(job_link, headers=headers, timeout=10)
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

    msg = MIMEMultipart()
    msg['From'] = EMAIL_SENDER
    msg['To'] = EMAIL_RECEIVER
    msg['Subject'] = f"Found {len(jobs)} High-Paying Government IT Jobs (> Rs. {BASELINE_SALARY})"

    html_content = f"<h2>Found {len(jobs)} jobs exceeding your baseline:</h2><ul>"
    for job in jobs:
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
