import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import Select
import datetime
import dateparser
import calendar
import pickle

# Set to True to get fresh results from web, 
# or False to read from pickle file
# (no need to keep reloading data while testing 
# data formatting options)
DATA_SOURCE_IS_WEB = False

# This should be filled in for first run
POSTCODE =""

# This part is just the first way I thought of to anonymise my postcode... 
# totally unnecessary for this to function
POSTCODE_FILENAME="postcode.pickle"
if POSTCODE == "" :
    # Load postcode from pickle file
    with open(POSTCODE_FILENAME, 'rb') as handle:
        POSTCODE = pickle.load(handle)
else:
    # Update saved postcode in pickle file
    with open(POSTCODE_FILENAME, 'wb') as handle:
        pickle.dump(POSTCODE, handle, protocol=pickle.HIGHEST_PROTOCOL)


FILENAME = 'data-backup.pickle'

if DATA_SOURCE_IS_WEB: # Get data from website
    # Set up webdriver options
    my_options = Options()

    # Block any popup notifications and automation warning
    my_options.add_experimental_option("prefs", {
        "profile.default_content_setting_values.notifications": 1
    })
    my_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    my_options.add_experimental_option('useAutomationExtension', False)

    # Create webdriver instance using chromedriver
    # chromedriver.exe will need to be available on PATH
    driver = webdriver.Chrome(options=my_options)

    # Get the website
    driver.get('https://ilambassadorformsprod.azurewebsites.net/wastecollectiondays/index')

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
    address_chooser_elem= driver.find_element_by_id("Uprn")
    address_chooser = Select(address_chooser_elem)
    address_chooser.select_by_index(1)

    # Wait a while for calendar to populate
    time.sleep(5)

    # Find elements corresponding to collection days
    days = driver.find_elements_by_class_name("rc-event-container")

    # Create list to hold our data
    binlist = []

    # Iterate over each found element
    for day in days:
        # Find the 'a' tag for each collection day text
        a = day.find_element_by_tag_name('a')
        
        # Parse the datetext attribute into date format
        bin_datetime=dateparser.parse(a.get_attribute("data-original-datetext"))
        bin_date = bin_datetime.date()

        # Get collection details string
        bin_desc=a.get_attribute("data-original-title")

        #append tuple of date and bins to our binlist
        binlist.append((bin_date, bin_desc))

    # Close driver as we don't need it any more
    driver.close()

    # Save a copy of binlist to pickle
    with open(FILENAME, 'wb') as handle:
        pickle.dump(binlist, handle, protocol=pickle.HIGHEST_PROTOCOL)

else: # Read data from pickle file
    with open(FILENAME, 'rb') as handle:
        binlist = pickle.load(handle)

# Consolidate by date
consolidated_list = []

# Iterate over source list
for bin_date, bin_desc in binlist:
    # To keep track of whether we have found date in destination list
    date_already_found=False

    # check if destination list is empty
    if len(consolidated_list) > 0:
        # Iterate over destination list
        for consolidated_entry in consolidated_list:
            # Check if source date matches destination date
            if consolidated_entry[0]==bin_date:
                # Set this as true so we don't create a new separate entry later
                date_already_found=True
                # Append source description to destination description list
                consolidated_entry[1].append(bin_desc)
                
    
    # Check if we have already appended this entry to an existing one
    if date_already_found==False:
        # Then we need to add a new entry
        consolidated_list.append([bin_date, [bin_desc]])

# Trim elapsed events
while(consolidated_list[0][0] < datetime.date.today()):
    consolidated_list.pop(0)

# Print list
for binday in consolidated_list:
    date_str = binday[0].strftime("%a, %d %b")
    bins_str = ", ".join(binday[1])
    print(date_str + " : " + bins_str)
