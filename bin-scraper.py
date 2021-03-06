import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import Select
import datetime
import dateparser
import pickle
import json
import os

# import calendar
# from pprint import pprint

# os.environ['DISPLAY'] = ':0.0'
os.environ['DISPLAY'] = ':0'


# Set to True to get fresh results from web,
# or False to read from pickle file
# (no need to keep reloading data while testing
# data formatting options)
DATA_SOURCE_IS_WEB = True
JSON_EXPORT_FILENAME = "/home/pi/code/bin-scraper/bin_list.json"

# This should be filled in for first run
POSTCODE = ""

# This part is just the first way I thought of to anonymise my postcode...
# totally unnecessary for this to function
POSTCODE_FILENAME = "/home/pi/code/bin-scraper/postcode.pickle"
if POSTCODE == "":
    # Load postcode from pickle file
    with open(POSTCODE_FILENAME, 'rb') as handle:
        POSTCODE = pickle.load(handle)
else:
    # Update saved postcode in pickle file
    with open(POSTCODE_FILENAME, 'wb') as handle:
        pickle.dump(POSTCODE, handle, protocol=pickle.HIGHEST_PROTOCOL)


DATA_BACKUP_FILENAME = '/home/pi/code/bin-scraper/data-backup.pickle'

if DATA_SOURCE_IS_WEB:  # Get data from website
    # Set up webdriver options
    my_options = Options()

    # Block any popup notifications and automation warning
    my_options.add_experimental_option("prefs", {
        "profile.default_content_setting_values.notifications": 1
    })
    my_options.add_experimental_option("excludeSwitches",
                                       ["enable-automation"])
    my_options.add_experimental_option('useAutomationExtension', False)

    # Create webdriver instance using chromedriver
    # chromedriver.exe will need to be available on PATH
    driver = webdriver.Chrome(options=my_options)

    # Get the website
    driver.get('https://ilambassadorformsprod.azurewebsites'
               '.net/wastecollectiondays/index')

    # Find the postcode field and fill it in
    postcode_field = driver.find_element_by_id('Postcode')
    postcode_field.click()
    postcode_field.send_keys(POSTCODE)

    # Find the "Find address" button and click it
    find_address_btn = driver.find_element_by_class_name('btn')
    find_address_btn.click()

    # Wait a while for dropdown list to populate
    time.sleep(5)

    # Find address dropdown and select second item in list
    # (no need to identify exact address for my particular
    # postcode as all addresses have the same collection day)
    address_chooser_elem = driver.find_element_by_id("Uprn")
    address_chooser = Select(address_chooser_elem)
    address_chooser.select_by_index(1)

    # Wait a while for calendar to populate
    time.sleep(5)

    # Create list to hold our data
    binlist = []

    # Find elements corresponding to collection days
    days = driver.find_elements_by_class_name("rc-event-container")

    # Iterate over each found element
    for day in days:
        # Find the 'a' tag for each collection day text
        a = day.find_element_by_tag_name('a')

        # Parse the datetext attribute into date format
        bin_datetime = dateparser.parse(a.get_attribute
                                        ("data-original-datetext"))
        bin_date = bin_datetime.date()

        # Get collection details string
        bin_desc = a.get_attribute("data-original-title")

        # Append tuple of date and bins to our binlist
        binlist.append((bin_date, bin_desc))

    # Find the "Next month" button and click it
    rc_next_btn = driver.find_element_by_class_name('rc-next')
    rc_next_btn.click()

    # Wait a while for next calendar month to populate
    time.sleep(5)

    # Find elements corresponding to collection days
    days = driver.find_elements_by_class_name("rc-event-container")

    # Iterate over each found element
    for day in days:
        # Find the 'a' tag for each collection day text
        a = day.find_element_by_tag_name('a')

        # Parse the datetext attribute into date format
        bin_datetime = dateparser.parse(a.get_attribute
                                        ("data-original-datetext"))
        bin_date = bin_datetime.date()

        # Get collection details string
        bin_desc = a.get_attribute("data-original-title")

        # Append tuple of date and bins to our binlist
        binlist.append((bin_date, bin_desc))

    # Close driver as we don't need it any more
    driver.close()

    # Save a copy of binlist to pickle
    with open(DATA_BACKUP_FILENAME, 'wb') as handle:
        pickle.dump(binlist, handle, protocol=pickle.HIGHEST_PROTOCOL)

else:  # Read data from pickle file
    with open(DATA_BACKUP_FILENAME, 'rb') as handle:
        binlist = pickle.load(handle)

# Consolidate by date
consolidated_list = []

# Iterate over source list
for bin_date, bin_desc in binlist:
    # To keep track of whether we have found date in destination list
    date_already_found = False

    # check if destination list is empty
    if len(consolidated_list) > 0:
        # Iterate over destination list
        for consolidated_entry in consolidated_list:
            # Check if source date matches destination date
            if consolidated_entry[0] == bin_date:
                # Set as true so we don't create a new separate entry later
                date_already_found = True
                # Append source description to destination description list
                consolidated_entry[1].append(bin_desc)

    # Check if we have already appended this entry to an existing one
    if date_already_found is False:
        # Then we need to add a new entry
        consolidated_list.append([bin_date, [bin_desc]])

# Trim elapsed events
while(consolidated_list[0][0] < datetime.date.today()):
    consolidated_list.pop(0)

# Trim event 5 and beyond
while(len(consolidated_list) > 5):
    consolidated_list.pop()

# Create list of dicts for easier json parsing later
export_list = []

for binday in consolidated_list:
    bintime = datetime.time(hour=7, minute=0)
    bin_dt = datetime.datetime.combine(binday[0], bintime)
    date_iso = bin_dt.isoformat()
    date_string = binday[0].strftime("%a %d/%m")  # 9 characters
    date_dict = {'date_string': date_string, 'date_iso': date_iso}

    binday[0] = date_dict
    binlen = len(binday[1])
    if binlen == 1:
        # only one collection this date
        desc = binday[1].pop()
        if "Household" in desc:
            binday[1] = ["Household"]
        elif "blue lidded" in desc:
            binday[1] = ["Recycling", "    Wheelie Bin Only"]
        elif "Black box" in desc:
            binday[1] = ["Recycling", "      Black box Only"]
        elif "garden" in desc:
            binday[1] = ["Garden"]
        else:
            #  unknown description - flag error with truncated desc
            binday[1] = ["ParseError", desc[0:19]]
    elif binlen == 2:
        # two collections - prob recycling, poss something non-std
        desc0 = binday[1].pop()
        desc1 = binday[1].pop()
        concat_desc = desc0+desc1
        if ("blue lid" in concat_desc) and ("Black box" in concat_desc):
            binday[1] = ["Recycling"]
        else:
            binday[1] = ["NONSTDERR2", desc0[0:19], desc1[0:19]]
    elif binlen > 2:
        # more than 2 collections - def something weird
        binday[1].insert(0, ("NONSTDERR" + binlen))
        for bin in binday:
            bin = bin[0:19]

    if "Garden" not in binday[1][0]:
        day_dict = {'date': binday[0], 'bins': binday[1]}

        export_list.append(day_dict)

        export_dict = {"bindates": export_list}

# json stringify
json_export_list = json.dumps(export_dict)

with open(JSON_EXPORT_FILENAME, 'w') as f:
    json.dump(json_export_list, f)


def print_list_of_dicts(list_of_dicts):
    print("")
    for bin_dict in list_of_dicts:
        print(f"Date: {bin_dict['date']}")
        print("Bins:")
        for bin_type in bin_dict['bins']:
            print(f"   --- {bin_type}")
    print("")


def test_reimport():
    print("")
    print("List of dicts (before exporting to json):")
    print_list_of_dicts(export_list)

    print("json string (before saving to disk)")
    print(json_export_list)

    with open('bin_list.json') as json_file:
        imported_file = json.load(json_file)

    print("")
    print("json string (as read back from disk)")
    print(imported_file)
    print("")

    imported_list = json.loads(imported_file)

    print("List of dicts (after importing back from json)")
    print_list_of_dicts(imported_list)

# Uncomment this to enable test printouts
# test_reimport()
