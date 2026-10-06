import requests
from dataclasses import dataclass
from urllib.parse import urljoin


@dataclass
class AccSetting:
    startDate: str
    endDate: str
    granularity: str

    def __post_init___(self):

        if self.enddate or self.startdate:
            if self.startdate:
                if not self.enddate:
                    raise Exception("Missing endDate")
            elif self.enddate:
                if not self.startdate:
                    raise Exception("Missing startDate")
            else:
                if self.startdate > self.endDate:
                    raise Exception(f"startDate is later then endDate")

        if self.granularity:
            self.granularity = self.granularity.capitalize()

    @classmethod
    def update_settings(cls, settings: dict):
        # update the settings from the page using dictionary
        pass


class AccountingAPI:
    def __init__(self, app, user):
        if hasattr(user, 'environment'):
            self.base_url = app.config.get('IRODS_ENVS', {}).get(user.environment, {}).get('accounting_api_url', '')
        else:
            self.base_url = ''

    def get_request(self, endpoint="report", params=None):
        """
        Makes a GET request to the API endpoint.
        Args:
            endpoint: The API endpoint to request.
            params: (optional) Parameters to include in the request.
        Returns:
            JSON response from the API.
        """
        url = urljoin(self.base_url, endpoint)
        response = requests.get(url, params=params, verify=False)

        if params:
            for para in params:
                # remove empty params
                if para == None:
                    del params[para]

        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(
                f"GET request to {url} failed with status code {response.status_code}"
            )


def list_departments(accounting_data):
    department_list = []
    for source_number, department_data in accounting_data["bucketed_usage"].items():
        for department in department_data:
            department_list.append(department)
    return department_list


def total_usage_perDepartment(accounting_data):
    """Sorts the data from accounting api to per department
    for display purposes in idms_web accounting dashboard.

    Args:
        data (dictionary): accounting data requested from the api

    Returns:
        dictionary: column and data in bootstraptable format
    """
    # total_usage is used for sorting the data
    total_usage = []
    # dashboard column/data is used for preping boostraptable
    dashboard_data = []
    dashboard_column = [
        {"field": "department", "title": "Department", "sortable": "true"}
    ]

    # # accumulate total usage
    for source_number, department_data in accounting_data["bucketed_usage"].items():
        accumulate_total_usage = {}

        # get the source
        for sources in accounting_data["sources"]:
            if int(source_number) != sources["id"]:
                continue
            # define de unit and the source
            source_unit, source_factor = sources["report_unit_factor"]
            source_instance = sources["source_instance"]
            # table column name
            source_title = f"{source_instance} ({source_unit})"

            # prep the table column
            column_template = {
                "field": f"{source_instance}",
                "title": f"{source_title}",
                "sortable": "true",
            }

            if column_template not in dashboard_column:
                dashboard_column.append(column_template)

        # aggregate and prep the data
        for department, users in department_data.items():

            accumulate_total_usage.setdefault(department, {})

            # now accumulate all the usage data
            for user in users:
                # total storage
                total_usage_per_user = users[user]["total"]
                # add user as key if accumulate doesnt have depa
                accumulate_total_usage[department].setdefault(source_instance, 0)
                accumulate_total_usage[department][source_instance] += float(
                    total_usage_per_user
                )

            # correct with the factor and set to 2 decimal
            accumulate_total_usage[department][
                source_instance
            ] = f"{accumulate_total_usage[department][source_instance] / source_factor : .2f}"

        total_usage.append(accumulate_total_usage)

    # prep table data
    for department_info in total_usage:
        for department in department_info:
            usage_data = department_info[department]

            # prep data view
            usage_data.update({"department": department})
            dashboard_data.append(usage_data)

    dashboard_display = {"column": dashboard_column, "data": dashboard_data}
    return dashboard_display


def total_userusage_perDeparment(accounting_data):
    """Sorts the data from accounting api to per department
    for display purposes in idms_web accounting dashboard.

    Args:
        department (string): department name
        data (dictionary)): accouting data from api

    Returns:
        dictionary: column and data in bootstraptable format
    """
    # pre-define dashboard column/data is used for preping boostraptable
    dashboard_data = []
    dashboard_column = [
        {
            "field": "user",
            "title": "User",
            "sortable": "true",
        }
    ]

    for source_number, department_data in accounting_data["bucketed_usage"].items():
        # get the source
        for sources in accounting_data["sources"]:

            if int(source_number) != sources["id"]:
                continue

            source_unit, source_factor = sources["report_unit_factor"]
            source_instance = sources["source_instance"]

            # table column name
            source = f"{source_instance} ({source_unit})"

            column_template = {
                "field": f"{source}",
                "title": f"{source.capitalize()}",
                "sortable": "true",
            }

            if column_template not in dashboard_column:
                dashboard_column.append(column_template)

        for users in department_data.values():
            aggegrate_usage_per_department = []
            for user in users:
                aggegrate_usage_per_user = {}
                # correct with the factor
                total_usage = users[user]["total"] / source_factor
                # prep the data for dashboard_data
                aggegrate_usage_per_user.setdefault(f"user", user)
                aggegrate_usage_per_user.setdefault(
                    f"{source}", f"{total_usage:.2f}"
                )  # if key not in temp, add in temp with value
                aggegrate_usage_per_department.append(aggegrate_usage_per_user)
            dashboard_data.append(aggegrate_usage_per_department)

    detailed_display = {"column": dashboard_column, "data": dashboard_data}
    return detailed_display