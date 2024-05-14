from __future__ import annotations

import json
import csv
import logging
import os
import random
import re
import time
from datetime import datetime, timedelta
import getpass
from pathlib import Path
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd
import pyautogui
import yaml
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from selenium.webdriver.chrome.service import Service as ChromeService
import webdriver_manager.chrome as ChromeDriverManager
ChromeDriverManager = ChromeDriverManager.ChromeDriverManager


log = logging.getLogger(__name__)


def setupLogger() -> None:
    dt: str = datetime.strftime(datetime.now(), "%m_%d_%y %H_%M_%S ")

    if not os.path.isdir('./logs'):
        os.mkdir('./logs')

    # TODO need to check if there is a log dir available or not
    logging.basicConfig(filename=('./logs/' + str(dt) + 'applyJobs.log'), filemode='w',
                        format='%(asctime)s::%(name)s::%(levelname)s::%(message)s', datefmt='./logs/%d-%b-%y %H:%M:%S')
    log.setLevel(logging.DEBUG)
    c_handler = logging.StreamHandler()
    c_handler.setLevel(logging.DEBUG)
    c_format = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', '%H:%M:%S')
    c_handler.setFormatter(c_format)
    log.addHandler(c_handler)


class EasyApplyBot:
    setupLogger()
    # MAX_SEARCH_TIME is 10 hours by default, feel free to modify it
    MAX_SEARCH_TIME = 60 * 60

    def __init__(self,
                 username,
                 password,
                 phone_number,
                 # profile_path,
                 salary,
                 rate,
                 uploads={},
                 filename='output.csv',
                 blacklist=[],
                 blackListTitles=[]) -> None:

        log.info("Welcome to Easy Apply Bot")
        dirpath: str = os.getcwd()
        log.info("current directory is : " + dirpath)

        self.uploads = uploads
        self.salary = salary
        self.rate = rate
        # self.profile_path = profile_path
        past_ids: list | None = self.get_appliedIDs(filename)
        self.appliedJobIDs: list = past_ids if past_ids != None else []
        self.filename: str = filename
        self.options = self.browser_options()
        self.browser = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=self.options)
        self.wait = WebDriverWait(self.browser, 30)
        self.blacklist = blacklist
        self.blackListTitles = blackListTitles
        self.start_linkedin(username, password)
        self.phone_number = phone_number


        self.locator = {
            "next": (By.CSS_SELECTOR, "button[aria-label='Continue to next step']"),
            "review": (By.CSS_SELECTOR, "button[aria-label='Review your application']"),
            "submit": (By.CSS_SELECTOR, "button[aria-label='Submit application']"),
            "error": (By.CLASS_NAME, "artdeco-inline-feedback__message"),
            "upload_resume": (By.XPATH, "//*[contains(@id, 'jobs-document-upload-file-input-upload-resume')]"),
            "upload_cv": (By.XPATH, "//*[contains(@id, 'jobs-document-upload-file-input-upload-cover-letter')]"),
            "follow": (By.CSS_SELECTOR, "label[for='follow-company-checkbox']"),
            "upload": (By.NAME, "file"),
            "search": (By.CLASS_NAME, "jobs-search-results-list"),
            "links": ("xpath", '//div[@data-job-id]'),
            "fields": (By.CLASS_NAME, "jobs-easy-apply-form-section__grouping"),
            "radio_select": (By.CSS_SELECTOR, "input[type='radio']"), #need to append [value={}].format(answer)
            "multi_select": (By.XPATH, "//*[contains(@id, 'text-entity-list-form-component')]"),
            "text_select": (By.CLASS_NAME, "artdeco-text-input--input"),
            "2fa_oneClick": (By.ID, 'reset-password-submit-button'),
            "easy_apply_button": (By.XPATH, '//button[contains(@class, "jobs-apply-button")]')

        }

        #initialize questions and answers file
        self.qa_file = Path("qa.csv")
        self.answers = {}

        #if qa file does not exist, create it
        if self.qa_file.is_file():
            df = pd.read_csv(self.qa_file)
            for index, row in df.iterrows():
                self.answers[row['Question']] = row['Answer']
        #if qa file does exist, load it
        else:
            df = pd.DataFrame(columns=["Question", "Answer"])
            df.to_csv(self.qa_file, index=False, encoding='utf-8')


    def get_appliedIDs(self, filename) -> list | None:
        try:
            df = pd.read_csv(filename,
                             header=None,
                             names=['timestamp', 'jobID', 'job', 'company', 'attempted', 'result'],
                             lineterminator='\n',
                             encoding='utf-8')

            df['timestamp'] = pd.to_datetime(df['timestamp'], format="%Y-%m-%d %H:%M:%S")
            df = df[df['timestamp'] > (datetime.now() - timedelta(days=2))]
            jobIDs: list = list(df.jobID)
            log.info(f"{len(jobIDs)} jobIDs found")
            return jobIDs
        except Exception as e:
            log.info(str(e) + "   jobIDs could not be loaded from CSV {}".format(filename))
            return None

    def browser_options(self):
        options = webdriver.ChromeOptions()
        options.add_argument("--start-maximized")
        options.add_argument("--ignore-certificate-errors")
        options.add_argument('--no-sandbox')
        options.add_argument("--disable-extensions")
        #options.add_argument(r'--remote-debugging-port=9222')
        #options.add_argument(r'--profile-directory=Person 1')

        # Disable webdriver flags or you will be easily detectable
        options.add_argument("--disable-blink-features")
        options.add_argument("--disable-blink-features=AutomationControlled")

        # Load user profile
        #options.add_argument(r"--user-data-dir={}".format(self.profile_path))
        return options

    def start_linkedin(self, username, password) -> None:
        log.info("Logging in.....Please wait :)  ")
        self.browser.get("https://www.linkedin.com/login?trk=guest_homepage-basic_nav-header-signin")
        try:
            user_field = self.browser.find_element("id","username")
            pw_field = self.browser.find_element("id","password")
            login_button = self.browser.find_element("xpath",
                        '//*[@id="organic-div"]/form/div[3]/button')
            user_field.send_keys(username)
            user_field.send_keys(Keys.TAB)
            time.sleep(2)
            pw_field.send_keys(password)
            time.sleep(2)
            login_button.click()
            time.sleep(15)
            # if self.is_present(self.locator["2fa_oneClick"]):
            #     oneclick_auth = self.browser.find_element(by='id', value='reset-password-submit-button')
            #     if oneclick_auth is not None:
            #         log.info("additional authentication required, sleep for 15 seconds so you can do that")
            #         time.sleep(15)
            # else:
            time.sleep(15)
        except TimeoutException:
            log.info("TimeoutException! Username/password field or login button not found")

    def fill_data(self) -> None:
        self.browser.set_window_size(1, 1)
        self.browser.set_window_position(2000, 2000)

    def start_apply(self, positions, locations) -> None:
        start: float = time.time()
        self.fill_data()
        self.positions = positions
        self.locations = locations
        combos: list = []
        while len(combos) < len(positions) * len(locations):
            position = positions[random.randint(0, len(positions) - 1)]
            location = locations[random.randint(0, len(locations) - 1)]
            combo: tuple = (position, location)
            if combo not in combos:
                combos.append(combo)
                log.info(f"Applying to {position}: {location}")
                location = "&location=" + location
                self.applications_loop(position, location)
            if len(combos) > 500:
                break

    # self.finish_apply() --> this does seem to cause more harm than good, since it closes the browser which we usually don't want, other conditions will stop the loop and just break out

    def applications_loop(self, position, location):

        count_application = 0
        count_job = 0
        jobs_per_page = 0
        start_time: float = time.time()

        log.info("Looking for jobs.. Please wait..")

        self.browser.set_window_position(1, 1)
        self.browser.maximize_window()
        self.browser, _ = self.next_jobs_page(position, location, jobs_per_page)
        log.info("Looking for jobs.. Please wait..")

        while time.time() - start_time < self.MAX_SEARCH_TIME:
            try:
                log.info(f"{(self.MAX_SEARCH_TIME - (time.time() - start_time)) // 60} minutes left in this search")

                # sleep to make sure everything loads, add random to make us look human.
                randoTime: float = random.uniform(1.5, 2.9)
                log.debug(f"Sleeping for {round(randoTime, 1)}")
                #time.sleep(randoTime)
                self.load_page(sleep=0.5)

                # LinkedIn displays the search results in a scrollable <div> on the left side, we have to scroll to its bottom

                # scroll to bottom

                if self.is_present(self.locator["search"]):
                    scrollresults = self.get_elements("search")
                    #     self.browser.find_element(By.CLASS_NAME,
                    #     "jobs-search-results-list"
                    # )
                    # Selenium only detects visible elements; if we scroll to the bottom too fast, only 8-9 results will be loaded into IDs list
                    for i in range(300, 3000, 100):
                        self.browser.execute_script("arguments[0].scrollTo(0, {})".format(i), scrollresults[0])
                    scrollresults = self.get_elements("search")
                    #time.sleep(1)

                # get job links, (the following are actually the job card objects)
                if self.is_present(self.locator["links"]):
                    links = self.get_elements("links")
                # links = self.browser.find_elements("xpath",
                #     '//div[@data-job-id]'
                # )

                    jobIDs = {} #{Job id: processed_status}
                
                    # children selector is the container of the job cards on the left
                    for link in links:
                            if 'Applied' not in link.text: #checking if applied already
                                if link.text not in self.blacklist: #checking if blacklisted
                                    jobID = link.get_attribute("data-job-id")
                                    if jobID == "search":
                                        log.debug("Job ID not found, search keyword found instead? {}".format(link.text))
                                        continue
                                    else:
                                        jobIDs[jobID] = "To be processed"
                    if len(jobIDs) > 0:
                        self.apply_loop(jobIDs)
                    self.browser, jobs_per_page = self.next_jobs_page(position,
                                                                      location,
                                                                      jobs_per_page)
                else:
                    self.browser, jobs_per_page = self.next_jobs_page(position,
                                                                      location,
                                                                      jobs_per_page)


            except Exception as e:
                print(e)
    def apply_loop(self, jobIDs):
        for jobID in jobIDs:
            if jobIDs[jobID] == "To be processed":
                applied = self.apply_to_job(jobID)
                if applied:
                    log.info(f"Applied to {jobID}")
                else:
                    log.info(f"Failed to apply to {jobID}")
                jobIDs[jobID] == applied

    def apply_to_job(self, jobID):
        # #self.avoid_lock() # annoying

        # get job page
        self.get_job_page(jobID)

        # let page load
        time.sleep(1)

        # get easy apply button
        button = self.get_easy_apply_button()


        # word filter to skip positions not wanted
        if button is not False:
            if any(word in self.browser.title for word in blackListTitles):
                log.info('skipping this application, a blacklisted keyword was found in the job position')
                string_easy = "* Contains blacklisted keyword"
                result = False
            else:
                string_easy = "* has Easy Apply Button"
                log.info("Clicking the EASY apply button")
                button.click()
                clicked = True
                time.sleep(1)
                self.fill_out_fields()
                result: bool = self.send_resume()
                if result:
                    string_easy = "*Applied: Sent Resume"
                else:
                    string_easy = "*Did not apply: Failed to send Resume"
        elif "You applied on" in self.browser.page_source:
            log.info("You have already applied to this position.")
            string_easy = "* Already Applied"
            result = False
        else:
            log.info("The Easy apply button does not exist.")
            string_easy = "* Doesn't have Easy Apply Button"
            result = False


        # position_number: str = str(count_job + jobs_per_page)
        log.info(f"\nPosition {jobID}:\n {self.browser.title} \n {string_easy} \n")

        self.write_to_file(button, jobID, self.browser.title, result)
        return result

    def write_to_file(self, button, jobID, browserTitle, result) -> None:
        def re_extract(text, pattern):
            target = re.search(pattern, text)
            if target:
                target = target.group(1)
            return target

        timestamp: str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        attempted: bool = False if button == False else True
        job = re_extract(browserTitle.split(' | ')[0], r"\(?\d?\)?\s?(\w.*)")
        company = re_extract(browserTitle.split(' | ')[1], r"(\w.*)")

        toWrite: list = [timestamp, jobID, job, company, attempted, result]
        with open(self.filename, 'a+') as f:
            writer = csv.writer(f)
            writer.writerow(toWrite)

    def get_job_page(self, jobID):

        job: str = 'https://www.linkedin.com/jobs/view/' + str(jobID)
        self.browser.get(job)
        self.job_page = self.load_page(sleep=0.5)
        return self.job_page

    def get_easy_apply_button(self):
        EasyApplyButton = False
        try:
            buttons = self.get_elements("easy_apply_button")
            # buttons = self.browser.find_elements("xpath",
            #     '//button[contains(@class, "jobs-apply-button")]'
            # )
            for button in buttons:
                if "Easy Apply" in button.text:
                    EasyApplyButton = button
                    self.wait.until(EC.element_to_be_clickable(EasyApplyButton))
                else:
                    log.debug("Easy Apply button not found")
            
        except Exception as e: 
            print("Exception:",e)
            log.debug("Easy Apply button not found")


        return EasyApplyButton

    def fill_out_fields(self):
         # Find all groupings in the form, which might contain any type of input field
        # form_sections = self.browser.find_elements(By.CLASS_NAME, "jobs-easy-apply-form-section__grouping")
        # # text_inputs = self.browser.find_elements(By.CSS_SELECTOR, "input[type='text']")
        # # for input_field in text_inputs:
        # #     input_field.clear()
        # #     input_field.send_keys('1')


        
        # for section in form_sections:
        #     # Handle text input fields
        #     text_inputs = section.find_elements(By.TAG_NAME, "input")
        #     for input_field in text_inputs:
        #         if input_field.get_attribute('type') == 'text':
        #             input_field.send_keys('1')  # Dynamically entering '1' for all text inputs

        #     # Handle radio buttons, specifically choosing 'Yes'
        #     radio_buttons = section.find_elements(By.XPATH, ".//input[@type='radio']")
        #     for radio in radio_buttons:
        #         label = self.browser.find_element(By.CSS_SELECTOR, f"label[for='{radio.get_attribute('id')}']").text
        #         if 'yes' in label.lower():
        #             radio.click()  # Selecting 'Yes' whenever available

        #     # Handle dropdown menus, selecting the first available option
        #     dropdowns = section.find_elements(By.TAG_NAME, "select")
        #     for dropdown in dropdowns:
        #         select = Select(dropdown)
        #         select.select_by_index(1)  # Select the first actual option (index 1, assuming index 0 is placeholder like "Select an option")

        fields = self.browser.find_elements(By.CLASS_NAME, "jobs-easy-apply-form-section__grouping")
        for field in fields:

            if "Mobile phone number" in field.text:
                field_input = field.find_element(By.TAG_NAME, "input")
                field_input.clear()
                field_input.send_keys(self.phone_number)


        return


    def get_elements(self, type) -> list:
        elements = []
        element = self.locator[type]
        if self.is_present(element):
            elements = self.browser.find_elements(element[0], element[1])
        return elements

    def is_present(self, locator):
        return len(self.browser.find_elements(locator[0],
                                              locator[1])) > 0

    def send_resume(self) -> bool:
        def is_present(button_locator) -> bool:
            return len(self.browser.find_elements(button_locator[0],
                                                  button_locator[1])) > 0

        try:
            #time.sleep(random.uniform(1.5, 2.5))
            next_locator = (By.CSS_SELECTOR,
                            "button[aria-label='Continue to next step']")
            review_locator = (By.CSS_SELECTOR,
                              "button[aria-label='Review your application']")
            submit_locator = (By.CSS_SELECTOR,
                              "button[aria-label='Submit application']")
            error_locator = (By.CLASS_NAME,"artdeco-inline-feedback__message")
            upload_resume_locator = (By.XPATH, '//span[text()="Upload resume"]')
            upload_cv_locator = (By.XPATH, '//span[text()="Upload cover letter"]')
            # WebElement upload_locator = self.browser.find_element(By.NAME, "file")
            follow_locator = (By.CSS_SELECTOR, "label[for='follow-company-checkbox']")

            submitted = False
            loop = 0
            while loop < 2:
                time.sleep(1)
                # Upload resume
                if is_present(upload_resume_locator):
                    #upload_locator = self.browser.find_element(By.NAME, "file")
                    try:
                        resume_locator = self.browser.find_element(By.XPATH, "//*[contains(@id, 'jobs-document-upload-file-input-upload-resume')]")
                        resume = self.uploads["Resume"]
                        resume_locator.send_keys(resume)
                    except Exception as e:
                        log.error(e)
                        log.error("Resume upload failed")
                        log.debug("Resume: " + resume)
                        log.debug("Resume Locator: " + str(resume_locator))
                # Upload cover letter if possible
                if is_present(upload_cv_locator):
                    cv = self.uploads["Cover Letter"]
                    cv_locator = self.browser.find_element(By.XPATH, "//*[contains(@id, 'jobs-document-upload-file-input-upload-cover-letter')]")
                    cv_locator.send_keys(cv)

                    #time.sleep(random.uniform(4.5, 6.5))
                elif len(self.get_elements("follow")) > 0:
                    elements = self.get_elements("follow")
                    for element in elements:
                        button = self.wait.until(EC.element_to_be_clickable(element))
                        button.click()

                if len(self.get_elements("submit")) > 0:
                    elements = self.get_elements("submit")
                    for element in elements:
                        button = self.wait.until(EC.element_to_be_clickable(element))
                        button.click()
                        log.info("Application Submitted")
                        submitted = True
                        break

                elif len(self.get_elements("error")) > 0:
                    elements = self.get_elements("error")
                    if "application was sent" in self.browser.page_source:
                        log.info("Application Submitted")
                        submitted = True
                        break
                    elif len(elements) > 0:
                        while len(elements) > 0:
                            log.info("Please answer the questions, waiting 5 seconds...")
                            time.sleep(5)
                            elements = self.get_elements("error")

                            for element in elements:
                                self.process_questions()

                            if "application was sent" in self.browser.page_source:
                                log.info("Application Submitted")
                                submitted = True
                                break
                            elif is_present(self.locator["easy_apply_button"]):
                                log.info("Skipping application")
                                submitted = False
                                break
                        continue
                        #add explicit wait
                    
                    else:
                        log.info("Application not submitted")
                        time.sleep(2)
                        break
                    # self.process_questions()

                elif len(self.get_elements("next")) > 0:
                    elements = self.get_elements("next")
                    for element in elements:
                        button = self.wait.until(EC.element_to_be_clickable(element))
                        button.click()

                elif len(self.get_elements("review")) > 0:
                    elements = self.get_elements("review")
                    for element in elements:
                        button = self.wait.until(EC.element_to_be_clickable(element))
                        button.click()

                elif len(self.get_elements("follow")) > 0:
                    elements = self.get_elements("follow")
                    for element in elements:
                        button = self.wait.until(EC.element_to_be_clickable(element))
                        button.click()

        except Exception as e:
            log.error(e)
            log.error("cannot apply to this job")
            pass
            #raise (e)

        return submitted
    



    # def process_questions(self):
    #     time.sleep(1)
    #     form_sections = self.get_elements("fields")

    #     for field in form_sections:
    #         question_text = field.text.split('\n')[0]  # Assume the question title is always first
    #         answer, answer_type = self.ans_question(question_text)

    #         if answer is None or answer_type is None:
    #             continue  # Skip if no actionable answer

    #         try:
    #             if answer_type == "text":
    #                 input_field = field.find_element(By.CSS_SELECTOR, "textarea, input[type='text']")
    #                 input_field.clear()
    #                 input_field.send_keys(answer)
    #             elif answer_type == "checkbox":
    #                 # Always click the first checkbox available
    #                 first_checkbox = field.find_element(By.CSS_SELECTOR, "input[type='checkbox']")
    #                 if not first_checkbox.is_selected():
    #                     first_checkbox.click()
    #             elif answer_type == "radio":
    #                 if answer == "default first":
    #                     first_radio_button = field.find_elements(By.CSS_SELECTOR, "input[type='radio']")
    #                     if first_radio_button:
    #                         first_radio_button[0].click()
    #                     else:
    #                         log.error(f"No radio buttons found for {question_text}")
    #                 else:
    #                     radio_button = field.find_element(By.XPATH, f".//label[contains(text(), '{answer}')]")
    #                     radio_button.click()
    #         except Exception as e:
    #             log.error(f"Error processing {question_text}: {str(e)}")

    # def process_questions(self):
    #     time.sleep(1)
    #     form_sections = self.get_elements("fields")

    #     for field in form_sections:
    #         question_text = field.text.split('\n')[0]  # Assume the question title is always first

    #         # Provide default answers based on field type
    #         if "text" in field.get_attribute("class"):
    #             input_field = field.find_element(By.TAG_NAME, "input")
    #             input_field.clear()
    #             input_field.send_keys('1')  # Dynamically entering '1' for all text inputs
    #         elif "checkbox" in field.get_attribute("class"):
    #             # Always click the first checkbox available
    #             first_checkbox = field.find_element(By.CSS_SELECTOR, "input[type='checkbox']")
    #             if not first_checkbox.is_selected():
    #                 first_checkbox.click()
    #         elif "radio" in field.get_attribute("class"):
    #             # Select the first radio button available
    #             first_radio_button = field.find_elements(By.CSS_SELECTOR, "input[type='radio']")
    #             if first_radio_button:
    #                 first_radio_button[0].click()
    #             else:
    #                 log.error(f"No radio buttons found for {question_text}")
    #         elif "select" in field.get_attribute("class"):
    #             # Select the first option in the dropdown
    #             dropdown = Select(field.find_element(By.TAG_NAME, "select"))
    #             dropdown.select_by_index(1)  # Select the first actual option (index 1, assuming index 0 is placeholder like "Select an option")
    #         else:
    #             log.error(f"Unsupported field type for question: {question_text}")

    # def process_questions(self):
    #     time.sleep(1)
    #     form_sections = self.get_elements("fields")

    #     for field in form_sections:
    #         question_text = field.text.split('\n')[0]  # Assume the question title is always first

    #         try:
    #             # Handle text input fields
    #             text_inputs = field.find_elements(By.CSS_SELECTOR, "textarea, input[type='text']")
    #             for input_field in text_inputs:
    #                 input_field.clear()
    #                 input_field.send_keys('1')  # Enter '1' for all text inputs

    #             # Handle radio buttons, select the first option
    #             radio_buttons = field.find_elements(By.XPATH, ".//input[@type='radio']")
    #             if radio_buttons:
    #                 radio_buttons[0].click()  # Select the first radio button

    #             # Handle dropdown menus, select the second option (index 1)
    #             dropdowns = field.find_elements(By.TAG_NAME, "select")
    #             for dropdown in dropdowns:
    #                 select = Select(dropdown)
    #                 select.select_by_index(1)  # Select the second option (index 1, assuming index 0 is placeholder like "Select an option")

    #         except Exception as e:
    #             log.error(f"Error processing {question_text}: {str(e)}")

    # def process_questions(self):
    #     time.sleep(1)
    #     form_sections = self.get_elements("fields")

    #     for field in form_sections:
    #         question_text = field.text.split('\n')[0]  # Assume the question title is always first
    #         log.info(f"Processing question: {question_text}")

    #         try:
    #             # Handle text input fields
    #             text_inputs = field.find_elements(By.CSS_SELECTOR, "textarea, input[type='text']")
    #             for input_field in text_inputs:
    #                 input_field.clear()
    #                 input_field.send_keys('1')  # Enter '1' for all text inputs
    #                 log.info(f"Entered '1' in text input field")

    #             # Handle radio buttons, select the first option
    #             radio_buttons = field.find_elements(By.XPATH, ".//input[@type='radio']")
    #             if radio_buttons:
    #                 radio_buttons[0].click()  # Select the first radio button
    #                 log.info(f"Selected the first radio button option")

    #             # Handle dropdown menus, select the second option (index 1)
    #             dropdowns = field.find_elements(By.TAG_NAME, "select")
    #             for dropdown in dropdowns:
    #                 select = Select(dropdown)
    #                 if len(select.options) > 1:
    #                     select.select_by_index(1)  # Select the second option (index 1, assuming index 0 is placeholder like "Select an option")
    #                     log.info(f"Selected the second dropdown option")

    #         except Exception as e:
    #             log.error(f"Error processing {question_text}: {str(e)}")

    def process_questions(self):
        time.sleep(1)
        form_sections = self.get_elements("fields")

        for field in form_sections:
            question_text = field.text.split('\n')[0]  # Assume the question title is always first
            log.info(f"Processing question: {question_text}")

            try:
                # Handle text input fields
                text_inputs = field.find_elements(By.CSS_SELECTOR, "textarea, input[type='text']")
                for input_field in text_inputs:
                    input_field.clear()
                    input_field.send_keys('1')  # Enter '1' for all text inputs
                    log.info(f"Entered '1' in text input field")

                # Handle radio buttons, select the first option
                radio_buttons = field.find_elements(By.XPATH, ".//input[@type='radio']")
                if radio_buttons:
                    first_radio_button = radio_buttons[0]
                    parent_label = self.browser.find_element(By.XPATH, f"//label[@for='{first_radio_button.get_attribute('id')}']")
                    parent_label.click()  # Click the label associated with the first radio button
                    log.info(f"Selected the first radio button option")

                # Handle dropdown menus, select the second option (index 1)
                dropdowns = field.find_elements(By.TAG_NAME, "select")
                for dropdown in dropdowns:
                    select = Select(dropdown)
                    if len(select.options) > 1:
                        select.select_by_index(1)  # Select the second option (index 1, assuming index 0 is placeholder like "Select an option")
                        log.info(f"Selected the second dropdown option")

            except Exception as e:
                log.error(f"Error processing {question_text}: {str(e)}")




   

    def ans_question(self, question):
        question_lower = question.lower()
        if "can you ensure availability during late hours" in question_lower or \
            "can you debug, build architectures and troubleshoot easily" in question_lower:
                return "default first", "checkbox"
        elif "do you have team management experience" in question_lower:
                return "Yes, extensive management experience in various projects.", "text"
        elif "do you have a cyber security certification" in question_lower:
                return "No", "text"  # If no specific certification, adjust accordingly
        elif "your title" in question_lower:
            return "Software Engineer", "text"
        elif "company" in question_lower:
            return "OpenAI", "text"
        elif "i currently work here" in question_lower:
            return "Yes", "checkbox"
        elif "dates of employment" in question_lower or "from" in question_lower:
            return {"month": "January", "year": "2020"}, "date"
        elif "to" in question_lower:
            return "Present", "text"
        elif "earliest start date" in question_lower:
            return "Within 0 to 30 days", "radio"
        elif "how many" in question_lower or "experience" in question_lower:
            return "1", "text"
        elif "sponsor" in question_lower:
            return "No", "radio"
        elif 'do you ' in question_lower or "are you " in question_lower or "have you " in question_lower or "open to contract based roles" in question_lower:
            return "Yes", "radio"  # Optimized for questions where "Yes" is likely an option
        elif "us citizen" in question_lower or "can you legally" in question_lower:
            return "Yes", "radio"
        elif "salary" in question_lower:
            return str(self.salary), "text"
        elif "can you" in question_lower:
            return "Yes", "radio"
        elif "gender" in question_lower or "race" in question_lower or "ethnicity" in question_lower or "lgbtq" in question_lower or "nationality" in question_lower:
            return "Prefer not to answer", "dropdown"
        elif "government" in question_lower:
            return "I do not wish to self-identify", "dropdown"
        elif "street address" in question_lower:
            return "123 Example St", "text"
        elif "city" in question_lower:
            return "Lahore, Punjab, Pakistan", "text"
        elif "state" in question_lower:
            return "Punjab", "text"
        elif "zip" in question_lower or "postal code" in question_lower:
            return "12345", "text"
        elif "desired salary" in question_lower:
            return "50000", "text"
        else:
            return "Yes", "radio", True  # Default to "Yes" if present, otherwise the first option








    def load_page(self, sleep=1):
        scroll_page = 0
        while scroll_page < 4000:
            self.browser.execute_script("window.scrollTo(0," + str(scroll_page) + " );")
            scroll_page += 500
            time.sleep(sleep)

        if sleep != 1:
            self.browser.execute_script("window.scrollTo(0,0);")
            time.sleep(sleep)

        page = BeautifulSoup(self.browser.page_source, "lxml")
        return page

    def avoid_lock(self) -> None:
        x, _ = pyautogui.position()
        pyautogui.moveTo(x + 200, pyautogui.position().y, duration=1.0)
        pyautogui.moveTo(x, pyautogui.position().y, duration=0.5)
        pyautogui.keyDown('ctrl')
        pyautogui.press('esc')
        pyautogui.keyUp('ctrl')
        time.sleep(0.5)
        pyautogui.press('esc')

    def next_jobs_page(self, position, location, jobs_per_page):
        self.browser.get(
            # URL for jobs page
            "https://www.linkedin.com/jobs/search/?f_LF=f_AL&keywords=" +
            position + location + "&start=" + str(jobs_per_page))
        #self.avoid_lock()
        log.info("Loading next job page?")
        self.load_page()
        return (self.browser, jobs_per_page)

    # def finish_apply(self) -> None:
    #     self.browser.close()


if __name__ == '__main__':

    with open("config.yaml", 'r') as stream:
        try:
            parameters = yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            raise exc

    assert len(parameters['positions']) > 0
    assert len(parameters['locations']) > 0
    assert parameters['username'] is not None
    assert parameters['password'] is not None
    assert parameters['phone_number'] is not None


    if 'uploads' in parameters.keys() and type(parameters['uploads']) == list:
        raise Exception("uploads read from the config file appear to be in list format" +
                        " while should be dict. Try removing '-' from line containing" +
                        " filename & path")

    log.info({k: parameters[k] for k in parameters.keys() if k not in ['username', 'password']})

    output_filename: list = [f for f in parameters.get('output_filename', ['output.csv']) if f is not None]
    output_filename: list = output_filename[0] if len(output_filename) > 0 else 'output.csv'
    blacklist = parameters.get('blacklist', [])
    blackListTitles = parameters.get('blackListTitles', [])

    uploads = {} if parameters.get('uploads', {}) is None else parameters.get('uploads', {})
    for key in uploads.keys():
        assert uploads[key] is not None

    locations: list = [l for l in parameters['locations'] if l is not None]
    positions: list = [p for p in parameters['positions'] if p is not None]

    bot = EasyApplyBot(parameters['username'],
                       parameters['password'],
                       parameters['phone_number'],
                       parameters['salary'],
                       parameters['rate'],
                       uploads=uploads,
                       filename=output_filename,
                       blacklist=blacklist,
                       blackListTitles=blackListTitles
                       )
    bot.start_apply(positions, locations)