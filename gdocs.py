import os
from datetime import datetime

import pygsheets

TODAY_YYYY_MM_DD = datetime.today().strftime('%Y-%m-%d')


def write_to_spreadsheet(data):
    spreadsheet = get_sheet()
    worksheet = spreadsheet.add_worksheet(TODAY_YYYY_MM_DD, index=0)
    worksheet.update_values(crange='A1', values=[['Last updated: ' + datetime.utcnow().isoformat() + 'Z']])
    worksheet.update_values(crange='A2', values=data)

    # Make the first two rows frozen & bold
    worksheet.frozen_rows = 2
    header = worksheet.range('A1:Z2')
    for row in header:
        for cell in row:
            cell.set_text_format('bold', True)
            cell.update()

    # Sort by name, then by price descending
    worksheet.sort_range('A3', 'Z999', basecolumnindex=1)
    worksheet.sort_range('A3', 'Z999', basecolumnindex=7, sortorder='DESCENDING')

    return spreadsheet.url;


def get_sheet():
    return get_client().open_by_key('1ecCAnxoc-zej-84ROFMerw88mglWrUrXvbbPJaDlKrg')


def get_client():
    service_account_file = os.environ['GDOCS_SERVICE_ACCOUNT_FILENAME']
    return pygsheets.authorize(service_account_file=service_account_file)


def main():
    1


if __name__ == '__main__':
    main()
