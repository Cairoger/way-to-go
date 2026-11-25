"""Exercise the installed release of Safari against the runner's disposable site."""

import platform

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.ui import WebDriverWait


def run(origin, username, password, invite_url, stop_site):
    with webdriver.Safari() as browser:
        wait = WebDriverWait(browser, 25)

        def css(selector):
            return wait.until(ec.visibility_of_element_located((By.CSS_SELECTOR, selector)))

        def click(label):
            xpath = f"//button[normalize-space(.)='{label}']"
            wait.until(ec.element_to_be_clickable((By.XPATH, xpath))).click()

        def visible(selector, value):
            wait.until(ec.text_to_be_present_in_element((By.CSS_SELECTOR, selector), value))

        print("Safari", browser.capabilities["browserVersion"], "macOS", platform.mac_ver()[0])
        browser.get(origin)
        click("建立旅程")
        css("input[name=username]").send_keys(username)
        css("input[name=password]").send_keys(password)
        click("使用測試帳號登入")
        visible("button.profile", username)
        browser.refresh()
        visible("button.profile", username)
        print("PASS: signed-in account persisted after reload")

        browser.get(invite_url)
        visible("button.profile", username)
        click("加入旅程")
        visible("main", "台南巷弄小旅行")
        click("行前清單")
        click("新增任務")
        css("[role=dialog] input[name=title]").send_keys("Safari 行李清點")
        click("儲存任務")
        visible(".prep-root", "Safari 行李清點")
        print("PASS: created a task from the preparation form")

        click("日期協調")
        click("標記我的日期")
        field = css("input[name=start]")
        # Use the ISO date value across macOS regional date-picker layouts.
        browser.execute_script("arguments[0].value = '2027-05-04'", field)
        click("儲存標記")
        visible("[role=status].dc-feedback", "已儲存日期標記")
        click("投票")
        css("input[name=choice]").click()
        click("送出選票")
        visible("main", "更新選票")
        print("PASS: saved availability and voted in a trip poll")

        click("每日行程")
        visible("main", "神農街")
        css("details.offline-trip > summary").click()
        click("儲存離線旅程")
        visible("details.offline-trip", "更新離線旅程")
        wait.until(lambda d: d.execute_script("return !!navigator.serviceWorker.controller"))
        trip_url = browser.current_url
        assert "trip=" in trip_url
        old_tab = browser.current_window_handle
        browser.switch_to.new_window("tab")
        fresh_tab = browser.current_window_handle
        browser.switch_to.window(old_tab)
        browser.close()
        browser.switch_to.window(fresh_tab)
        stop_site()
        browser.get(trip_url)
        visible("body", "離線唯讀")
        visible("body", "神農街")
        visible("body", "中西區神農街")
        assert not browser.find_elements(By.TAG_NAME, "button")
        print("PASS: opened the saved read-only trip in a new tab with its HTTP server stopped")
