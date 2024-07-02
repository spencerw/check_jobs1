from dotenv import load_dotenv
import os
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium_stealth import stealth
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.core.os_manager import ChromeType
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import pandas as pd

def configure_webdriver():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("start-maximized")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager(chrome_type=ChromeType.CHROMIUM).install()), options=options)
    stealth(driver,
            languages=["en-US", "en"],
            vendor="Google Inc.",
            platform="Win32",
            webgl_vendor="Intel Inc.",
            renderer="Intel Iris OpenGL Engine",
            fix_hairline=True,
            )

    return driver


def search_jobs(driver, country, job_position, job_location, date_posted):
    full_url = f'{country}/jobs?q={"+".join(job_position.split())}&l={job_location}&fromage={date_posted}'
    print(full_url)
    driver.get(full_url)
    global total_jobs
    try:
        job_count_element = driver.find_element(By.XPATH,
                                                '//div[starts-with(@class, "jobsearch-JobCountAndSortPane-jobCount")]')
        total_jobs = job_count_element.find_element(By.XPATH, './span').text
        print(f"{total_jobs} found")
    except NoSuchElementException:
        print("No job count found")
        total_jobs = "Unknown"

    return full_url


def scrape_job_data(driver, country):
    df = pd.DataFrame({'Link': [''], 'Job Title': [''], 'Company': [''],
                       'Date Posted': [''], 'Location': ['']})
    job_count = 0
    # count = 0
    while True:
        # count += 1
        soup = BeautifulSoup(driver.page_source, 'lxml')

        boxes = soup.find_all('div', class_='job_seen_beacon')

        for i in boxes:
            link = i.find('a').get('href')
            link_full = country + link
            job_title = i.find('a', class_='jcs-JobTitle css-jspxzf eu4oa1w0').text
            # Check if the 'Company' attribute exists
            company_tag = i.find('span', {'data-testid': 'company-name'})
            company = company_tag.text if company_tag else None

            try:
                date_posted = i.find('span', class_='date').text
            except AttributeError:
                date_posted = i.find('span', {'data-testid': 'myJobsStateDate'}).text.strip()

            location_element = i.find('div', {'data-testid': 'text-location'})
            location = ''
            if location_element:
                # Check if the element contains a span
                span_element = location_element.find('span')

                if span_element:
                    location = span_element.text
                else:
                    location = location_element.text

            new_data = pd.DataFrame({'Link': [link_full], 'Job Title': [job_title],
                                     'Company': [company],
                                     'Date Posted': [date_posted],
                                     'Location': [location]})

            df = pd.concat([df, new_data], ignore_index=True)
            job_count += 1

        print(f"Scraped {job_count} of {total_jobs}")

        try:
            next_page = soup.find('a', {'aria-label': 'Next Page'}).get('href')

            next_page = country + next_page
            driver.get(next_page)

        except:
            break

    return df

load_dotenv()

# Email credentials and settings from environment variables
SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587
EMAIL_ADDRESS = os.getenv('EMAIL_ADDRESS')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')
TO_ADDRESS = os.getenv('TO_ADDRESS')

driver = configure_webdriver()
job_position = 'Data Scientist'
job_location = 'San+Diego%2C+CA'
date_posted = 1

full_url = search_jobs(driver, 'https://www.indeed.com', job_position, job_location, date_posted)
df = scrape_job_data(driver, 'https://www.indeed.com')[['Job Title', 'Link']][1:]
print('Found ' + str(len(df)) + ' listed jobs')
print(df)

if os.path.exists('jobs.csv'):
	df_prev = pd.read_csv('jobs.csv')
else:
	df_prev = pd.DataFrame(columns=['Job Title', 'Link'])
print('Found ' + str(len(df_prev)) + ' existing jobs')
prev_links = set(df_prev['Link'])
df_new = df[~df['Link'].isin(prev_links)]
print('Found ' + str(len(df_new)) + ' new jobs')
df_updated = pd.concat([df_prev, df_new])
df.to_csv('jobs.csv', index=False)

# Send an email if there are any new jobs
if len(df_new) > 0:
    # Create the email content
    msg = MIMEMultipart()
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = TO_ADDRESS
    msg['Subject'] = 'New Indeed Data Scientist Jobs'
    body = ''
    for _, row in df_new.iterrows():
        body += f"<p><a href='{row['Link']}'>{row['Job Title']}</a></p>"
    msg.attach(MIMEText(body, 'html'))

    # Connect to the SMTP server and send the email
    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.sendmail(EMAIL_ADDRESS, TO_ADDRESS, msg.as_string())
        server.quit()
        print("Email sent successfully.")
    except Exception as e:
        print(f"Failed to send email: {e}")