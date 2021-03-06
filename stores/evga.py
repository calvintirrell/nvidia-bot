import json
from os import path
from time import sleep

from chromedriver_py import binary_path  # this will get you the path variable
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.ui import WebDriverWait

import pickle

from notifications.notifications import NotificationHandler
from utils import selenium_utils
from utils.logger import log
from utils.selenium_utils import options, enable_headless

LOGIN_URL = "https://secure.evga.com/us/login.asp"
CONFIG_PATH = "evga_config.json"


class Evga:
    def __init__(self, headless=False):
        if headless:
            enable_headless()
        self.driver = webdriver.Chrome(executable_path=binary_path, options=options)
        self.credit_card = {}
        self.card_pn = ""
        self.card_series = ""
        try:
            if path.exists(CONFIG_PATH):
                with open(CONFIG_PATH) as json_file:
                    config = json.load(json_file)
                    username = config["username"]
                    password = config["password"]
                    self.card_pn = config["card_pn"]
                    self.card_series = config["card_series"]
                    self.credit_card["name"] = config["credit_card"]["name"]
                    self.credit_card["number"] = config["credit_card"]["number"]
                    self.credit_card["cvv"] = config["credit_card"]["cvv"]
                    self.credit_card["expiration_month"] = config["credit_card"][
                        "expiration_month"
                    ]
                    self.credit_card["expiration_year"] = config["credit_card"][
                        "expiration_year"
                    ]
        except Exception as e:
            log.error(f"This is most likely an error with your {CONFIG_PATH} file.")
            raise e

        self.login(username, password)

    def login(self, username, password):
        """
        We're just going to attempt to load cookies, else enter the user info and let the user handle the captcha
        :param username:
        :param password:
        :return:
        """
        self.driver.execute_cdp_cmd(
            "Network.setUserAgentOverride",
            {
                "userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.53 Safari/537.36"
            },
        )
        self.driver.execute_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

        if path.isfile("evga-cookies.pkl"):  # check for cookies file
            self.driver.get("https://www.evga.com")
            selenium_utils.wait_for_page(
                self.driver, "EVGA - Intelligent Innovation - Official Website", 300
            )
            cookies = pickle.load(open("evga-cookies.pkl", "rb"))
            for cookie in cookies:
                self.driver.add_cookie(cookie)

        self.driver.get("https://www.evga.com")
        selenium_utils.wait_for_page(
            self.driver, "EVGA - Intelligent Innovation - Official Website", 300
        )
        if (
            len(self.driver.find_elements_by_id("svg-login")) > 0
        ):  # cookies did not provide logged in state
            self.driver.get(LOGIN_URL)
            selenium_utils.wait_for_page(self.driver, "EVGA - Intelligent Innovation")

            selenium_utils.field_send_keys(self.driver, "evga_login", username)
            selenium_utils.field_send_keys(self.driver, "password", password)

            log.info("Go do the captcha and log in")

            selenium_utils.wait_for_page(
                self.driver, "EVGA - Intelligent Innovation - Official Website", 300
            )
            pickle.dump(
                self.driver.get_cookies(), open("evga-cookies.pkl", "wb")
            )  # save cookies

        log.info("Logged in!")

    def buy(self, delay=5, test=False, model=""):
        if test:
            log.info("Refreshing Page Until Title Matches ...")
            selenium_utils.wait_for_title(
                self.driver,
                "EVGA - Products - Graphics - GeForce 16 Series Family - GTX 1660",
                "https://www.evga.com/products/ProductList.aspx?type=0&family=GeForce+16+Series+Family&chipset=GTX+1660",
            )
        else:
            log.info("Refreshing Page Until Title Matches ...")
            selenium_utils.wait_for_title(
                self.driver,
                "EVGA - Products - Graphics - GeForce 30 Series Family - RTX "
                + self.card_series,
                "https://www.evga.com/products/productlist.aspx?type=0&family=GeForce+30+Series+Family&chipset=RTX+"
                + self.card_series,
            )

        log.info("matched chipset=RTX+" + self.card_series + "!")

        # check for card
        log.info("On GPU list Page")
        card_btn = self.driver.find_elements_by_xpath(
            "//a[@href='/products/product.aspx?pn=" + self.card_pn + "']"
        )
        while not card_btn:
            log.debug("Refreshing page for GPU")
            self.driver.refresh()
            card_btn = self.driver.find_elements_by_xpath(
                "//a[@href='/products/product.aspx?pn=" + self.card_pn + "']"
            )
            sleep(delay)

        card_btn[0].click()

        #  Check for stock
        log.info("On GPU Page")
        atc_buttons = self.driver.find_elements_by_xpath(
            '//input[@class="btnBigAddCart"]'
        )
        while not atc_buttons:
            log.debug("Refreshing page for GPU")
            self.driver.refresh()
            atc_buttons = self.driver.find_elements_by_xpath(
                '//input[@class="btnBigAddCart"]'
            )
            sleep(delay)

        #  Add to cart
        atc_buttons[0].click()

        #  Go to checkout
        selenium_utils.wait_for_page(self.driver, "EVGA - Checkout")
        selenium_utils.button_click_using_xpath(
            self.driver, '//*[@id="LFrame_CheckoutButton"]'
        )

        # Shipping Address screen
        selenium_utils.wait_for_page(self.driver, "Shopping")

        log.info("Skip that page.")
        self.driver.get("https://secure.evga.com/Cart/Checkout_Payment.aspx")

        selenium_utils.wait_for_page(self.driver, "EVGA - Checkout - Billing Options")

        log.info("Ensure that we are paying with credit card")
        sleep(1)  # Fix this.
        WebDriverWait(self.driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, './/input[@value="rdoCreditCard"]'))
        ).click()
        WebDriverWait(self.driver, 10).until(
            EC.element_to_be_clickable(
                (By.XPATH, '//*[@id="ctl00_LFrame_btncontinue"]')
            )
        ).click()

        selenium_utils.wait_for_element(self.driver, "ctl00_LFrame_txtNameOnCard")

        log.info("Populate credit card fields")

        selenium_utils.field_send_keys(
            self.driver, "ctl00$LFrame$txtNameOnCard", self.credit_card["name"]
        )
        selenium_utils.field_send_keys(
            self.driver, "ctl00$LFrame$txtCardNumber", self.credit_card["number"]
        )
        selenium_utils.field_send_keys(
            self.driver, "ctl00$LFrame$txtCvv", self.credit_card["cvv"]
        )
        Select(self.driver.find_element_by_id("ctl00_LFrame_ddlMonth")).select_by_value(
            self.credit_card["expiration_month"]
        )
        Select(self.driver.find_element_by_id("ctl00_LFrame_ddlYear")).select_by_value(
            self.credit_card["expiration_year"]
        )
        WebDriverWait(self.driver, 10).until(
            EC.element_to_be_clickable(
                (
                    By.XPATH,
                    "/html/body/form/div[3]/div[3]/div/div[1]/div[5]/div[3]/div/div[1]/div/div[@id='checkoutButtons']/input[2]",
                )
            )
        ).click()

        log.info("Finalize Order Page")
        selenium_utils.wait_for_page(self.driver, "EVGA - Checkout - Finalize Order")

        WebDriverWait(self.driver, 10).until(
            EC.element_to_be_clickable((By.ID, "ctl00_LFrame_cbAgree"))
        ).click()

        selenium_utils.wait_for_element(self.driver, "ctl00_LFrame_btncontinue")

        if not test:
            WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.ID, "ctl00_LFrame_btncontinue"))
            ).click()

        log.info("Finalized Order!")
