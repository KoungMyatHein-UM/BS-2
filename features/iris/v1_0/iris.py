from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from jinja2 import Template
from app.core.contracts.feature_interface import BaseFeature
from app.core.easy_options import EasyOptions

import time
import os

def register():
    instance = Feature()

    easy_options = EasyOptions("IRIS Image Search Options:")
    easy_options.add_option("google_search", "Google Reverse Image Search", instance.google_reverse_search)
    easy_options.add_option("yandex_search", "Yandex Reverse Image Search", instance.yandex_reverse_search)
    easy_options.add_option("tineye_search", "TinEye Reverse Image Search", instance.tineye_reverse_search)
    easy_options.add_option("bing_search", "Bing Reverse Image Search", instance.bing_reverse_search)

    return {
        "instance": instance,
        "self_test": instance.self_test,
        "shutdown": instance.shutdown,
        "easy_options": easy_options,
    }

class Feature(BaseFeature):
    def __init__(self):
        self.driver = None
        self.max_results = 0
        self.search_timeout = 0

    def self_test(self):
        """Test if Chrome/Chromium is available for Selenium"""
        try:
            # Try to create a headless driver briefly
            chrome_options = Options()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            
            test_driver = webdriver.Chrome(options=chrome_options)
            test_driver.quit()
            return True
        except Exception as e:
            print(f"IRIS self-test failed: {e}")
            return False

    def shutdown(self):
        """Close any active browser sessions"""
        if self.driver:
            try:
                self.driver.quit()
                print("IRIS: Browser session closed")
            except:
                pass
        print("Shutting down IRIS...")

    def run_default(self, params: dict) -> str:
        """Default method - runs Google reverse image search"""
        return self.google_reverse_search(params)

    def _setup_driver(self, headless: bool = False):
        """Set up Chrome webdriver with stealth options"""
        chrome_options = Options()
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_experimental_option("prefs", {"intl.accept_languages": "en-US,en"})
        
        if headless:
            chrome_options.add_argument("--headless")
        
        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    def google_reverse_search(self, params: dict) -> str:
        """Perform Google reverse image search"""
        file_path = params.get("file_path")
        if not file_path or not os.path.isfile(file_path):
            return "<p>No file selected or invalid path.</p>"

        try:
            self._setup_driver()
            
            # Navigate to Google Images
            self.driver.get("https://images.google.com?hl=en&gl=us")
            # time.sleep(3)
            
            # Handle cookie consent if present
            self._handle_cookie_consent()
            
            # Click on the camera icon for reverse image search
            camera_button = WebDriverWait(self.driver, 0).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "[aria-label*='Search by image']"))
            )
            camera_button.click()
            
            # Find upload button
            upload_tab = self._find_upload_button()
            if upload_tab:
                upload_tab.click()
            
            # Find and use the file input
            file_input = WebDriverWait(self.driver, 0).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='file']"))
            )
            file_input.send_keys(os.path.abspath(file_path))
            
            # Wait for search results to load
            WebDriverWait(self.driver, self.search_timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "[data-ved]"))
            )
            # time.sleep(3)
            
            # Get the current URL for the results
            results_url = self.driver.current_url
            
            # Extract some basic result information
            try:
                result_elements = self.driver.find_elements(By.CSS_SELECTOR, "[data-ved]")
                result_count = len(result_elements)
            except:
                result_count = 0

            template_str = """
            <style>
                .iris-container {
                    font-family: 'Segoe UI', 'Roboto', 'Arial', sans-serif;
                    max-width: 100%;
                    margin: 20px 0;
                }
                .search-info {
                    background-color: #e8f5e8;
                    border-left: 4px solid #28a745;
                    padding: 15px 20px;
                    margin: 15px 0;
                    border-radius: 4px;
                }
                .search-results {
                    background-color: #f8f9fa;
                    border: 1px solid #e9ecef;
                    border-radius: 8px;
                    padding: 20px;
                    margin: 15px 0;
                }
                .browser-note {
                    background-color: #fff3cd;
                    border-left: 4px solid #ffc107;
                    padding: 15px 20px;
                    margin: 15px 0;
                    border-radius: 4px;
                }
                .iris-title {
                    color: #2c3e50;
                    border-bottom: 2px solid #007bff;
                    padding-bottom: 10px;
                    margin-bottom: 20px;
                }
                .url-link {
                    color: #007bff;
                    text-decoration: none;
                    word-break: break-all;
                }
                .url-link:hover {
                    text-decoration: underline;
                }
            </style>
            <div class="iris-container">
                <h2 class="iris-title">🔍 IRIS - Google Reverse Image Search</h2>
                <div class="search-info">
                    <strong>📁 Image File:</strong> <code>{{ filename }}</code><br>
                    <strong>🔍 Search Engine:</strong> Google Images<br>
                    <strong>📊 Results Found:</strong> {{ result_count }} elements detected
                </div>
                
                <div class="search-results">
                    <h3>✅ Search Completed Successfully</h3>
                    <p><strong>Results URL:</strong> <a href="{{ results_url }}" target="_blank" class="url-link">{{ results_url }}</a></p>
                    <p>The reverse image search has been completed. You can:</p>
                    <ul>
                        <li>🌐 <strong>View Results:</strong> Click the URL above to open results in a new tab</li>
                        <li>🔍 <strong>Analyze Similar Images:</strong> Look for visually similar content</li>
                        <li>📄 <strong>Check Source Pages:</strong> Find websites containing this image</li>
                        <li>🏷️ <strong>Identify Objects:</strong> Use Google's automatic object recognition</li>
                    </ul>
                </div>
                
                <div class="browser-note">
                    <strong>💡 Tip:</strong> For best results, try different reverse image search engines like Yandex, TinEye, or Bing using the other IRIS options.
                </div>
            </div>
            """

            template = Template(template_str)
            return template.render(
                filename=os.path.basename(file_path),
                results_url=results_url,
                result_count=result_count
            )

        except Exception as e:
            if self.driver:
                self.driver.quit()
                self.driver = None
            return f"<p>❌ Error during Google reverse image search: {str(e)}</p>"

    def yandex_reverse_search(self, params: dict) -> str:
        """Perform Yandex reverse image search"""
        file_path = params.get("file_path")
        if not file_path or not os.path.isfile(file_path):
            return "<p>No file selected or invalid path.</p>"

        try:
            self._setup_driver()
            
            # Navigate to Yandex Images
            self.driver.get("https://yandex.com/images/")
            time.sleep(3)
            
            # Find and click the camera icon
            camera_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, ".CameraButton"))
            )
            camera_button.click()
            
            # Upload file
            file_input = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='file']"))
            )
            file_input.send_keys(os.path.abspath(file_path))
            
            # Wait for results
            time.sleep(5)
            results_url = self.driver.current_url

            template_str = """
            <div class="iris-container">
                <h2 class="iris-title">🔍 IRIS - Yandex Reverse Image Search</h2>
                <div class="search-info">
                    <strong>📁 Image File:</strong> <code>{{ filename }}</code><br>
                    <strong>🔍 Search Engine:</strong> Yandex Images<br>
                    <strong>✅ Status:</strong> Search completed
                </div>
                <div class="search-results">
                    <h3>✅ Yandex Search Completed</h3>
                    <p><strong>Results URL:</strong> <a href="{{ results_url }}" target="_blank" class="url-link">{{ results_url }}</a></p>
                    <p>Yandex often provides different results than Google, especially for:</p>
                    <ul>
                        <li>🌍 Content from Eastern Europe and Russia</li>
                        <li>📷 Better face recognition capabilities</li>
                        <li>🏢 Architectural and landmark identification</li>
                    </ul>
                </div>
            </div>
            """

            template = Template(template_str)
            return template.render(
                filename=os.path.basename(file_path),
                results_url=results_url
            )

        except Exception as e:
            if self.driver:
                self.driver.quit()
                self.driver = None
            return f"<p>❌ Error during Yandex reverse image search: {str(e)}</p>"
            

    def tineye_reverse_search(self, params: dict) -> str:
        """Perform TinEye reverse image search"""
        file_path = params.get("file_path")
        if not file_path or not os.path.isfile(file_path):
            return "<p>No file selected or invalid path.</p>"

        try:
            self._setup_driver()
            
            # Navigate to TinEye
            self.driver.get("https://tineye.com/")
            time.sleep(3)
            
            # Upload file
            file_input = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='file']"))
            )
            file_input.send_keys(os.path.abspath(file_path))
            
            # Wait for results
            time.sleep(5)
            results_url = self.driver.current_url

            template_str = """
            <div class="iris-container">
                <h2 class="iris-title">🔍 IRIS - TinEye Reverse Image Search</h2>
                <div class="search-info">
                    <strong>📁 Image File:</strong> <code>{{ filename }}</code><br>
                    <strong>🔍 Search Engine:</strong> TinEye<br>
                    <strong>✅ Status:</strong> Search completed
                </div>
                <div class="search-results">
                    <h3>✅ TinEye Search Completed</h3>
                    <p><strong>Results URL:</strong> <a href="{{ results_url }}" target="_blank" class="url-link">{{ results_url }}</a></p>
                    <p>TinEye specializes in:</p>
                    <ul>
                        <li>🕒 Finding the oldest version of an image online</li>
                        <li>📊 Showing image usage timeline</li>
                        <li>🔍 Exact duplicate detection</li>
                        <li>📈 Tracking image modifications and edits</li>
                    </ul>
                </div>
            </div>
            """

            template = Template(template_str)
            return template.render(
                filename=os.path.basename(file_path),
                results_url=results_url
            )

        except Exception as e:
            return f"<p>❌ Error during TinEye reverse image search: {str(e)}</p>"
        finally:
            if self.driver:
                self.driver.quit()
                self.driver = None

    def bing_reverse_search(self, params: dict) -> str:
        """Perform Bing reverse image search"""
        file_path = params.get("file_path")
        if not file_path or not os.path.isfile(file_path):
            return "<p>No file selected or invalid path.</p>"

        try:
            self._setup_driver()
            
            # Navigate to Bing Images
            self.driver.get("https://www.bing.com/images")
            time.sleep(3)
            
            # Find and click the camera icon
            camera_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, ".cameraSvg, [aria-label*='visual search']"))
            )
            camera_button.click()
            
            # Upload file
            file_input = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='file']"))
            )
            file_input.send_keys(os.path.abspath(file_path))
            
            # Wait for results
            time.sleep(5)
            results_url = self.driver.current_url

            template_str = """
            <div class="iris-container">
                <h2 class="iris-title">🔍 IRIS - Bing Visual Search</h2>
                <div class="search-info">
                    <strong>📁 Image File:</strong> <code>{{ filename }}</code><br>
                    <strong>🔍 Search Engine:</strong> Bing Visual Search<br>
                    <strong>✅ Status:</strong> Search completed
                </div>
                <div class="search-results">
                    <h3>✅ Bing Visual Search Completed</h3>
                    <p><strong>Results URL:</strong> <a href="{{ results_url }}" target="_blank" class="url-link">{{ results_url }}</a></p>
                    <p>Bing Visual Search excels at:</p>
                    <ul>
                        <li>🛍️ Product identification and shopping results</li>
                        <li>🏷️ Object and brand recognition</li>
                        <li>📍 Location and landmark identification</li>
                        <li>👥 Celebrity and public figure recognition</li>
                    </ul>
                </div>
            </div>
            """

            template = Template(template_str)
            return template.render(
                filename=os.path.basename(file_path),
                results_url=results_url
            )

        except Exception as e:
            return f"<p>❌ Error during Bing reverse image search: {str(e)}</p>"
        finally:
            if self.driver:
                self.driver.quit()
                self.driver = None

    def _find_upload_button(self):
        """Helper method to find upload button using multiple selectors"""
        upload_selectors = [
            "//div[contains(text(), 'Upload a file')]",
            "//div[contains(text(), 'upload a file')]", 
            "//div[contains(text(), 'Upload an image')]",
            "//span[contains(text(), 'Upload a file')]",
            "//span[contains(text(), 'upload a file')]",
            "//button[contains(text(), 'Upload')]",
            "//div[@role='tab'][contains(., 'Upload')]",
            "//div[contains(@class, 'upload')]",
            "[data-bucket='upload']"
        ]
        
        for selector in upload_selectors:
            try:
                if selector.startswith("//"):
                    element = WebDriverWait(self.driver, 0).until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                else:
                    element = WebDriverWait(self.driver, 0).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                return element
            except:
                continue
        return None

    def _handle_cookie_consent(self):
        """Handle Google's cookie consent dialog"""
        try:
            consent_selectors = [
                "button[id*='accept']",
                "button[id*='agree']",
                "button[id*='Accept all']",
                "button[class*='accept']",
                "button[class*='agree']",
                "div[role='button'][jsaction*='accept']"
            ]
            
            for selector in consent_selectors:
                try:
                    buttons = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for button in buttons:
                        if button.is_displayed() and button.is_enabled():
                            button.click()
                            time.sleep(1)
                            return
                except:
                    continue
        except Exception as e:
            pass  # Consent handling is optional