import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import csv
import json
from urllib.parse import quote
import re

def scroll_to_load_all_jobs(driver, scroll_pause=2, max_scrolls=10):
    last_height = driver.execute_script("return document.body.scrollHeight")
    for i in range(max_scrolls):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(scroll_pause)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            print(f"[INFO] Reached end of the page after {i+1} scrolls.")
            break
        last_height = new_height
    print("[INFO] Finished scrolling.")

def login_and_navigate(driver, url):
    print("[INFO] Opening Naukri recommended jobs page...")
    driver.get(url)
    print("[INFO] Please manually log in if required.")
    WebDriverWait(driver, 60).until(
        EC.presence_of_all_elements_located((By.XPATH, '//article[contains(@class, "jobTuple")]'))
    )
    print("[INFO] Jobs loaded, proceeding with scrolling.")
    scroll_to_load_all_jobs(driver, scroll_pause=2, max_scrolls=15)
    print("[INFO] Finished scrolling, ready to scrape.")

def search_company_info_selenium(company_name, driver):
    """Search for company website and LinkedIn using Selenium on Google"""
    if not company_name:
        return "", ""
    
    website = ""
    linkedin = ""
    
    try:
        # Search Google for website
        search_query = quote(f"{company_name} official website")
        driver.get(f"https://www.google.com/search?q={search_query}")
        time.sleep(1.5)
        
        # Try multiple selectors for search results
        try:
            # Method 1: Try modern Google search result selectors
            result_divs = driver.find_elements(By.CSS_SELECTOR, 'div.g')
            
            for div in result_divs[:10]:
                try:
                    # Get the main link from this result
                    link = div.find_element(By.CSS_SELECTOR, 'a')
                    href = link.get_attribute('href')
                    
                    if not href or not href.startswith('http'):
                        continue
                    
                    # Skip unwanted domains
                    exclude = ['google.', 'youtube.', 'facebook.', 'twitter.', 'instagram.', 
                               'wikipedia.', 'indeed.', 'naukri.', 'glassdoor.', 'ambitionbox.',
                               'linkedin.', 'payscale.', 'comparably.']
                    
                    if any(ex in href.lower() for ex in exclude):
                        continue
                    
                    # Clean URL (remove parameters)
                    clean_url = href.split('?')[0].split('#')[0]
                    if len(clean_url) < 100:  # Reasonable URL length
                        website = clean_url
                        print(f"      [DEBUG] Found website: {website}")
                        break
                
                except:
                    continue
            
            # Method 2: If no results, try getting all links
            if not website:
                all_links = driver.find_elements(By.TAG_NAME, 'a')
                for link in all_links[:30]:
                    try:
                        href = link.get_attribute('href')
                        if not href or not href.startswith('http'):
                            continue
                        
                        exclude = ['google.', 'youtube.', 'facebook.', 'twitter.', 'instagram.', 
                                   'wikipedia.', 'indeed.', 'naukri.', 'glassdoor.', 'ambitionbox.',
                                   'linkedin.', 'payscale.', 'comparably.', 'support.google', 'accounts.google']
                        
                        if any(ex in href.lower() for ex in exclude):
                            continue
                        
                        # Check if it looks like a company website
                        if '.' in href and len(href) < 100:
                            website = href.split('?')[0].split('#')[0]
                            print(f"      [DEBUG] Found website (fallback): {website}")
                            break
                    except:
                        continue
        except Exception as e:
            print(f"      [DEBUG] Website extraction error: {str(e)[:50]}")
        
        # Search for LinkedIn with site: operator for better results
        search_query = quote(f"{company_name} site:linkedin.com/company")
        driver.get(f"https://www.google.com/search?q={search_query}")
        time.sleep(1.5)
        
        try:
            # Method 1: Try to find LinkedIn in search results divs
            result_divs = driver.find_elements(By.CSS_SELECTOR, 'div.g')
            
            for div in result_divs[:5]:
                try:
                    link = div.find_element(By.CSS_SELECTOR, 'a')
                    href = link.get_attribute('href')
                    
                    if href and 'linkedin.com/company/' in href:
                        # Extract clean LinkedIn URL
                        match = re.search(r'(https://[^/\s]*linkedin\.com/company/[a-zA-Z0-9-]+)', href)
                        if match:
                            linkedin = match.group(1)
                            # Normalize to www.linkedin.com
                            linkedin = re.sub(r'https://[a-z]{2}\.linkedin\.com', 'https://www.linkedin.com', linkedin)
                            print(f"      [DEBUG] Found LinkedIn: {linkedin}")
                            break
                except:
                    continue
            
            # Method 2: If not found, search all visible text and links
            if not linkedin:
                page_source = driver.page_source
                # Look for LinkedIn URL in page source
                match = re.search(r'https://[^/\s"]*linkedin\.com/company/([a-zA-Z0-9-]+)', page_source)
                if match:
                    company_id = match.group(1)
                    linkedin = f"https://www.linkedin.com/company/{company_id}"
                    print(f"      [DEBUG] Found LinkedIn (from source): {linkedin}")
            
            # Method 3: Try all links as last resort
            if not linkedin:
                all_links = driver.find_elements(By.TAG_NAME, 'a')
                for link in all_links[:30]:
                    try:
                        href = link.get_attribute('href')
                        if href and 'linkedin.com/company/' in href:
                            match = re.search(r'(https://[^/\s]*linkedin\.com/company/[a-zA-Z0-9-]+)', href)
                            if match:
                                linkedin = match.group(1)
                                linkedin = re.sub(r'https://[a-z]{2}\.linkedin\.com', 'https://www.linkedin.com', linkedin)
                                print(f"      [DEBUG] Found LinkedIn (fallback): {linkedin}")
                                break
                    except:
                        continue
        except Exception as e:
            print(f"      [DEBUG] LinkedIn extraction error: {str(e)[:50]}")
        
    except Exception as e:
        print(f"[WARNING] Search failed for {company_name}: {str(e)[:80]}")
    
    return website, linkedin

def batch_search_companies(companies, driver):
    """Search for all companies in one browser tab session"""
    print(f"\n[INFO] Batch searching for {len(companies)} unique companies...")
    results = {}
    
    # Save current window
    main_window = driver.current_window_handle
    
    try:
        # Open one new tab for all searches
        driver.execute_script("window.open('');")
        driver.switch_to.window(driver.window_handles[-1])
        
        for i, company in enumerate(companies, 1):
            if company and company not in results:
                print(f"[INFO] [{i}/{len(companies)}] Searching: {company}")
                website, linkedin = search_company_info_selenium(company, driver)
                results[company] = {'website': website, 'linkedin': linkedin}
                print(f"      → Website: {'✓ ' + website if website else '✗ Not found'}")
                print(f"      → LinkedIn: {'✓ ' + linkedin if linkedin else '✗ Not found'}")
        
        # Close search tab
        driver.close()
        driver.switch_to.window(main_window)
        
    except Exception as e:
        print(f"[ERROR] Batch search failed: {e}")
        # Make sure we're back on main window
        try:
            if len(driver.window_handles) > 1:
                driver.close()
            driver.switch_to.window(driver.window_handles[0])
        except:
            pass
    
    return results

def scrape_jobs(driver):
    jobs = []
    job_cards = driver.find_elements(By.XPATH, '//article[contains(@class, "jobTuple")]')
    print(f"[INFO] Found {len(job_cards)} job cards.")
    
    # First pass: collect all company names
    unique_companies = set()
    temp_job_data = []

    for i, job in enumerate(job_cards, 1):
        # Debug: print the full HTML for the first few cards
        if i <= 3:
            print(f"\n[DEBUG] Job {i} HTML:\n{job.get_attribute('outerHTML')[:1500]}")

        # Title extraction
        try:
            title = job.find_element(By.XPATH, './/a[contains(@class, "title")]').get_attribute('textContent').strip()
        except:
            try:
                title = job.find_element(By.XPATH, './/p[contains(@class, "title")]').get_attribute('textContent').strip()
            except Exception as e:
                print(f"[ERROR] Title extraction for job {i}: {e}")
                title = ""

        # Company extraction - multiple fallback methods
        company = ""
        try:
            # Method 1: Look for subtitle with ellipsis
            company_elem = job.find_element(By.XPATH, './/span[contains(@class, "subTitle") or contains(@class, "subtitle")]')
            company = company_elem.get_attribute('textContent').strip()
        except:
            try:
                # Method 2: Look for company info class
                company_elem = job.find_element(By.XPATH, './/a[contains(@class, "comp-name") or contains(@class, "companyInfo")]')
                company = company_elem.get_attribute('textContent').strip()
            except:
                try:
                    # Method 3: Look for any element with title attribute containing company
                    company_elem = job.find_element(By.XPATH, './/*[@title and contains(@class, "comp")]')
                    company = company_elem.get_attribute('title').strip()
                except Exception as e:
                    print(f"[ERROR] Company extraction for job {i}: {e}")

        # Location extraction - multiple methods
        location = ""
        try:
            # Method 1: Look for location-specific class
            loc_elem = job.find_element(By.XPATH, './/span[contains(@class, "location") or contains(@class, "loc")]')
            location = loc_elem.get_attribute('textContent').strip()
        except:
            try:
                # Method 2: Look for li element with location
                loc_elem = job.find_element(By.XPATH, './/li[contains(@class, "location")]')
                location = loc_elem.get_attribute('textContent').strip()
            except:
                try:
                    # Method 3: Look for icon followed by text (common pattern)
                    loc_elem = job.find_element(By.XPATH, './/*[contains(@class, "ni-job-tuple-icon-srp-location")]//following-sibling::span')
                    location = loc_elem.get_attribute('textContent').strip()
                except:
                    try:
                        # Method 4: Look in the experience/salary row
                        row_elem = job.find_element(By.XPATH, './/div[contains(@class, "row") or contains(@class, "experienceContainer")]')
                        spans = row_elem.find_elements(By.TAG_NAME, 'span')
                        for span in spans:
                            text = span.get_attribute('textContent').strip()
                            # Location typically contains city names or "Remote"
                            if any(indicator in text.lower() for indicator in ['remote', 'bangalore', 'mumbai', 'delhi', 'pune', 'hyderabad', 'chennai', 'kolkata', 'india']):
                                location = text
                                break
                    except Exception as e:
                        print(f"[ERROR] Location extraction for job {i}: {e}")

        # Description extraction
        try:
            try:
                description = job.find_element(By.XPATH, './/div[contains(@class, "job-description")]/span').get_attribute('textContent').strip()
            except:
                description = job.find_element(By.XPATH, './/div[contains(@class, "job-description")]').get_attribute('textContent').strip()
        except:
            try:
                # Alternative: look for tags/skills section
                description = job.find_element(By.XPATH, './/ul[contains(@class, "tags")]').get_attribute('textContent').strip()
            except Exception as e:
                print(f"[ERROR] Description extraction for job {i}: {e}")
                description = ""

        # Store temporary data
        temp_job_data.append({
            'title': title,
            'company': company,
            'location': location,
            'description': description
        })
        
        # Collect unique company names
        if company:
            unique_companies.add(company)
    
    # Second pass: batch search all companies at once
    print(f"\n[INFO] Extracted {len(temp_job_data)} jobs from {len(unique_companies)} unique companies")
    company_info_cache = batch_search_companies(list(unique_companies), driver)
    
    # Third pass: build final job data with company info
    print(f"\n[INFO] Building final job data...")
    for i, temp_data in enumerate(temp_job_data, 1):
        company = temp_data['company']
        
        # Get company info from cache
        website = ""
        linkedin = ""
        if company and company in company_info_cache:
            website = company_info_cache[company]['website']
            linkedin = company_info_cache[company]['linkedin']

        jobs.append({
            "Job Title": temp_data['title'],
            "Company Name": company,
            "Website": website,
            "LinkedIn URL": linkedin,
            "Location": temp_data['location'],
            "Job Description": temp_data['description']
        })
        print(f"[INFO] Job {i}: {temp_data['title']} | {company} | {temp_data['location']}")
    
    return jobs

def export_to_csv(data, filename="naukri_jobs.csv"):
    if not data:
        print("[WARNING] No data to export to CSV.")
        return
    try:
        with open(filename, "w", newline='', encoding="utf-8") as out_csv:
            writer = csv.DictWriter(out_csv, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)
        print(f"[INFO] Data exported to CSV file: {filename}")
    except Exception as e:
        print(f"[ERROR] Failed to export CSV: {e}")

def export_to_json(data, filename="naukri_jobs.json"):
    if not data:
        print("[WARNING] No data to export to JSON.")
        return
    try:
        with open(filename, "w", encoding="utf-8") as out_json:
            json.dump(data, out_json, indent=2, ensure_ascii=False)
        print(f"[INFO] Data exported to JSON file: {filename}")
    except Exception as e:
        print(f"[ERROR] Failed to export JSON: {e}")

if __name__ == "__main__":
    url = "https://www.naukri.com/mnjuser/recommendedjobs"
    options = uc.ChromeOptions()
    options.headless = False  # Show browser for login

    try:
        print("[INFO] Starting undetected ChromeDriver...")
        driver = uc.Chrome(options=options)
        login_and_navigate(driver, url)
        print("\n[INFO] Starting job scraping with company info lookup...")
        job_data = scrape_jobs(driver)
    except Exception as main_e:
        print(f"[ERROR] Exception during scraping process: {main_e}")
        import traceback
        traceback.print_exc()
        job_data = []
    finally:
        driver.quit()
        print("[INFO] ChromeDriver closed.")

    if job_data:
        export_to_csv(job_data)
        export_to_json(job_data)
        print(f"\n[SUCCESS] Scraped {len(job_data)} jobs successfully!")
    else:
        print("[INFO] No job data scraped, no files created.")










