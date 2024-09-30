from seleniumbase import Driver
from time import sleep
from seleniumbase import Driver
from bs4 import BeautifulSoup
from datetime import datetime
from sys import path
from concurrent.futures import ThreadPoolExecutor
import os
import pandas as pd
import secrets
import logging
import re
import boto3
import time
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By


page_url= 'https://batdongsan.com.vn/nha-dat-ban'

#create multiple Chrome WebDriver instances.
def createChromeDriver(num_chrome):
    chrome_drivers = []
    for _ in range(num_chrome):
        driver = Driver(uc_cdp=True, incognito=False,block_images=True,headless=True)
        chrome_drivers.append(driver)
    return chrome_drivers


#getting URLs for each listing in single page
def extract_property_urls_single_page(page_url,html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    base_url= page_url
    property_urls=[base_url+element.get('href') for element in soup.select('.js__product-link-for-product-id')]
    return property_urls

#coordinates extraction
def extract_coordinates(html_content):
    # Define a regular expression pattern to extract coordinates
    pattern = r'place\?q=([-+]?\d*\.\d+),([-+]?\d*\.\d+)'

    # Use re.search to find the first match in the HTML content
    match = re.search(pattern, html_content)

    # Check if a match is found
    if match:
        # Extract latitude and longitude from the matched groups
        latitude = float(match.group(1))
        longitude = float(match.group(2))
        return [latitude, longitude]
    else:
        return [None,None]
    
def process_single_property(property_url,chrome_driver):
    # logging.info(property_url)
    chrome_driver.get(property_url)
    
    html_content = chrome_driver.page_source
    soup = BeautifulSoup(html_content, 'html.parser')
    # Find property info
    elements =  soup.find('div', class_='re__pr-specs-content js__other-info')
    titles=elements.find_all('span', class_='re__pr-specs-content-item-title')
    titles=[title.get_text() for title in titles]
    values=elements.find_all('span', class_='re__pr-specs-content-item-value')
    values=[value.get_text() for value in values]

    # Find property address
    address= soup.find('span', class_='re__pr-short-description js__pr-address').text
    titles.append("Địa chỉ")
    values.append(address)

    # Find property map coordination
    map_coor=soup.find('div', class_='re__section re__pr-map js__section js__li-other')
    map_coor=extract_coordinates(str(map_coor))
    titles.append("latitude")
    titles.append("longtitude")
    values.append(map_coor[0])
    values.append(map_coor[1])
    
    #Find url img
    specific_portion = soup.find('div', class_='slick-track')
    if (specific_portion):
        img_tags = specific_portion.find_all('img')
        jpg_urls = [img['data-src'] for img in img_tags if img.has_attr('data-src') and img['data-src'].endswith('.jpg')]
        titles.append("url ảnh")
        values.append(jpg_urls)
    
    # Number and Zalo contact and gmail 
   
   
    email_link = soup.find('a', class_='link_mail')
    if (email_link):
        data_href = email_link.get('data-href')
        email_address = re.search(r'mailto:(.*?)(\?|$)', data_href).group(1)
        titles.append("gmail")
        values.append(email_address)


    # Find date info
   
    short_info=soup.find('div', class_='re__pr-short-info re__pr-config js__pr-config')
    short_info_titles=short_info.find_all('span', class_='title')
    short_info_titles=[title.get_text() for title in short_info_titles]
    short_info_values=short_info.find_all('span', class_='value')
    short_info_values=[value.get_text() for value in short_info_values]
  
    
    # Merge 2 list
    titles.extend(short_info_titles)
    values.extend(short_info_values)


    property_attribute=dict(zip(titles, values))
    order_attribbute={}

    all_attributes = [
        "Diện tích","Mức giá",
        "Mặt tiền","Đường vào",
        "Hướng nhà","Hướng ban công",
        "Số tầng","Số phòng ngủ",
        "Số toilet","Pháp lý","Nội thất",
        'Ngày đăng', 'Ngày hết hạn',
        'Loại tin', 'Mã tin', 'Địa chỉ',
        "latitude","longtitude","SDT liên hệ","url ảnh","Zalo contact","gmail"
    ]
    all_attributes = {key: None for key in all_attributes}

    for attr in all_attributes:
        if(attr not in property_attribute):
            order_attribbute[attr]=None
        else:
            order_attribbute[attr]=property_attribute[attr]

    order_attribbute['url']=property_url

    return order_attribbute

def process_single_page(page_url,chrome_driver,max_retry=1):
    logging.info(f"The process's scrapping {page_url}...")
    for attempt in range(max_retry + 1):
        try:
            chrome_driver.get(page_url)

            # Check for Cloudflare bot detection
            if "Cloudflare" in chrome_driver.page_source:
                raise Exception("Cloudflare detected in the page source")

            # Scrapping data for each property
            html_content = chrome_driver.page_source
            property_urls = extract_property_urls_single_page(page_url,html_content)
            return property_urls
        except Exception as e:
            logging.info(f"Attempt {attempt + 1}: Error - {e}, try again in 5s")
            sleep(5)

    logging.info(f"All attempts failed. Returning None for {page_url}")
    return None

def process_multiple_pages(number_of_page,url,number_of_chrome_driver):

  chrome_driver_lst= createChromeDriver(number_of_chrome_driver)
  
  for i in range(1,number_of_page+1):
    properties= []
    page_url = f"{url}/p{i}"
    
    print(f"Scraping data from {page_url}")

    chrome_driver= secrets.choice(chrome_driver_lst)
    single_page_listing= process_single_page(page_url,chrome_driver,max_retry=1)

    for p in single_page_listing:
      properties.append(process_single_property(p,chrome_driver))
    apt_listing= pd.DataFrame(properties)
    csv_file_path = f'apt_listing_page_{i}.csv'
    apt_listing.to_csv(csv_file_path, index=False)
    # Upload CSV file to S3 bucket
    # Remove the local CSV file after uploading to S3
  print("Success")    


if __name__ == "__main__":
  result = process_multiple_pages(8435, page_url, 1)


