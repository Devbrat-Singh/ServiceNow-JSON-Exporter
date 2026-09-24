from fastapi import FastAPI, Request, HTTPException
def handle_servicenow_error(response):
    """
    Convert common ServiceNow API errors into
    clear application-level errors.
    """

    if response.status_code == 400:
        raise HTTPException(
            status_code=400,
            detail="Invalid request sent to ServiceNow."
        )

    if response.status_code == 401:
        raise HTTPException(
            status_code=401,
            detail="ServiceNow authentication failed or the access token has expired."
        )

    if response.status_code == 403:
        raise HTTPException(
            status_code=403,
            detail="Access denied. You do not have permission to access this ServiceNow resource."
        )

    if response.status_code == 404:
        raise HTTPException(
            status_code=404,
            detail="The requested ServiceNow table or resource was not found."
        )

    if response.status_code == 429:
        raise HTTPException(
            status_code=429,
            detail="ServiceNow rate limit reached. Please try again later."
        )

    if 500 <= response.status_code <= 599:
        raise HTTPException(
            status_code=502,
            detail="ServiceNow returned a server error. Please try again later."
        )

    raise HTTPException(
        status_code=response.status_code,
        detail="ServiceNow request failed."
    )
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
import httpx
import json
from typing import Literal
from pydantic import BaseModel, Field
from config import CORS_ORIGINS

from config import SERVICENOW_INSTANCE
from oauth import (
    generate_state,
    get_authorization_url,
    exchange_code_for_token,
    refresh_access_token,
)


app = FastAPI(
    title="ServiceNow JSON Data Exporter",
    description="External ServiceNow data export application",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[CORS_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================================================
# TEMPORARY DEVELOPMENT STORAGE
# =========================================================

# Stores OAuth states temporarily
oauth_states = set()

# Stores access token temporarily
access_token = None
refresh_token = None


# =========================================================
# REFRESH ACCESS TOKEN
# =========================================================

def refresh_service_now_token():
    global access_token, refresh_token

    if not refresh_token:
        raise HTTPException(
            status_code=401,
            detail="Session expired. Please login again."
        )

    try:
        token_data = refresh_access_token(refresh_token)

        new_access_token = token_data.get("access_token")

        if not new_access_token:
            raise Exception(
                "New access token was not returned by ServiceNow."
            )

        access_token = new_access_token

        # ServiceNow may return a new refresh token.
        new_refresh_token = token_data.get("refresh_token")

        if new_refresh_token:
            refresh_token = new_refresh_token

        return access_token

    except Exception:
        access_token = None
        refresh_token = None

        raise HTTPException(
            status_code=401,
            detail="Session expired. Please login again."
        )


# =========================================================
# SENSITIVE FIELD PROTECTION
# =========================================================

SENSITIVE_FIELD_NAMES = {
    "password",
    "user_password",
    "password_hash",
    "api_key",
    "access_token",
    "refresh_token",
    "client_secret",
    "private_key",
    "secret_key",
}


def is_sensitive_field(field_name: str) -> bool:
    """
    Determine whether a field should be blocked from export.
    """

    normalized_name = field_name.strip().lower()

    # Exact sensitive field names
    if normalized_name in SENSITIVE_FIELD_NAMES:
        return True

    # Sensitive naming patterns
    sensitive_patterns = (
        "password",
        "client_secret",
        "private_key",
        "access_token",
        "refresh_token",
    )

    return any(
        pattern in normalized_name
        for pattern in sensitive_patterns
    )

# =========================================================
# ROOT
# =========================================================

@app.get("/")
def root():
    return {
        "application": "ServiceNow JSON Data Exporter",
        "status": "running",
        "servicenow_instance": SERVICENOW_INSTANCE
    }


# =========================================================
# LOGIN
# =========================================================

@app.get("/login")
def login():

    # Generate random OAuth state
    state = generate_state()

    # Store state on backend
    oauth_states.add(state)

    # Build ServiceNow OAuth authorization URL
    authorization_url = get_authorization_url(state)

    return RedirectResponse(url=authorization_url)


# =========================================================
# OAUTH CALLBACK
# =========================================================

@app.get("/auth/callback")
def auth_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None
):

    global access_token, refresh_token

    # -----------------------------------------------------
    # Check authorization code
    # -----------------------------------------------------

    if not code:
        raise HTTPException(
            status_code=400,
            detail="Authorization code missing"
        )

    # -----------------------------------------------------
    # Check state
    # -----------------------------------------------------

    if not state:
        raise HTTPException(
            status_code=400,
            detail="State parameter missing from ServiceNow callback"
        )

    # -----------------------------------------------------
    # Validate state
    # -----------------------------------------------------

    if state not in oauth_states:
        raise HTTPException(
            status_code=400,
            detail="Invalid OAuth state"
        )

    # State successfully validated
    oauth_states.remove(state)

    # -----------------------------------------------------
    # Exchange authorization code for access token
    # -----------------------------------------------------

    try:

        token_data = exchange_code_for_token(code, state)

        # Store access token temporarily
        access_token = token_data.get("access_token")
        refresh_token = token_data.get("refresh_token")

        if not access_token:
            raise Exception(
                "Access token was not returned by ServiceNow"
            )

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=f"Token exchange failed: {str(e)}"
        )

    # -----------------------------------------------------
    # OAuth success response
    # -----------------------------------------------------

    return {
        "message": "OAuth authentication successful",
        "code_received": True,
        "state_valid": True,
        "token_received": True,
        "token_type": token_data.get("token_type"),
        "expires_in": token_data.get("expires_in")
    }


# =========================================================
# TEST INCIDENT API
# =========================================================

@app.get("/test/incident")
def test_incident_api():

    # Check authentication
    if not access_token:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated with ServiceNow. Please login first."
        )

    # ServiceNow Incident Table API
    url = f"{SERVICENOW_INSTANCE}/api/now/table/incident"

    # Request parameters
    params = {
        "sysparm_limit": 5
    }

    # Request headers
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json"
    }

    # Call ServiceNow
    try:

        response = httpx.get(
            url,
            headers=headers,
            params=params,
            timeout=30.0
        )

    except httpx.RequestError as e:

        raise HTTPException(
            status_code=502,
            detail=f"Could not connect to ServiceNow: {str(e)}"
        )

    # Check ServiceNow response
    if response.status_code != 200:

        raise HTTPException(
            status_code=response.status_code,
            detail=response.text
        )

    # Return ServiceNow JSON
    return response.json()


# =========================================================
# DYNAMIC TABLE DISCOVERY
# =========================================================
@app.get("/tables")
def get_tables():

    # Check authentication
    if not access_token:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated with ServiceNow. Please login first."
        )

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json"
    }

    # Dictionary:
    # table name -> table information
    table_map = {}

    try:

        # =====================================================
        # 1. GET TABLES FROM sys_db_object
        # =====================================================

        db_object_url = (
            f"{SERVICENOW_INSTANCE}/api/now/table/sys_db_object"
        )

        offset = 0
        page_size = 100

        while True:

            params = {
                "sysparm_fields": "name,label",
                "sysparm_limit": page_size,
                "sysparm_offset": offset,
                "sysparm_query": "nameISNOTEMPTY"
            }

            response = httpx.get(
                db_object_url,
                headers=headers,
                params=params,
                timeout=30.0
            )

            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=response.text
                )

            data = response.json()
            results = data.get("result", [])

            if not results:
                break

            for table in results:

                name = table.get("name")

                if not name:
                    continue

                table_map[name] = {
                    "name": name,
                    "label": table.get("label") or name
                }

            if len(results) < page_size:
                break

            offset += page_size


        # =====================================================
        # 2. GET TABLE NAMES FROM sys_dictionary
        # =====================================================

        dictionary_url = (
            f"{SERVICENOW_INSTANCE}/api/now/table/sys_dictionary"
        )

        offset = 0
        page_size = 500

        while True:

            params = {
                "sysparm_fields": "name",
                "sysparm_limit": page_size,
                "sysparm_offset": offset,
                "sysparm_query": "nameISNOTEMPTY"
            }

            response = httpx.get(
                dictionary_url,
                headers=headers,
                params=params,
                timeout=30.0
            )

            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=response.text
                )

            data = response.json()
            results = data.get("result", [])

            if not results:
                break

            for field in results:

                table_name = field.get("name")

                if not table_name:
                    continue

                # Add only if sys_db_object did not already provide it
                if table_name not in table_map:

                    table_map[table_name] = {
                        "name": table_name,
                        "label": table_name
                    }

            if len(results) < page_size:
                break

            offset += page_size


    except httpx.RequestError as e:

        raise HTTPException(
            status_code=502,
            detail=f"Could not connect to ServiceNow: {str(e)}"
        )


    # =========================================================
    # 3. CONVERT DICTIONARY TO LIST
    # =========================================================

    tables = list(table_map.values())

    # Sort alphabetically by label
    tables.sort(
        key=lambda table: table["label"].lower()
    )


    # =========================================================
    # 4. RETURN RESULT
    # =========================================================

    return {
        "count": len(tables),
        "tables": tables
    }


# =========================================================
# SEARCH SERVICE NOW TABLES
# =========================================================

@app.get("/tables/search")
def search_tables(query: str):

    # Check authentication
    if not access_token:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated with ServiceNow. Please login first."
        )

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json"
    }

    table_map = {}

    try:

        # =====================================================
        # 1. SEARCH sys_db_object
        # =====================================================

        db_object_url = (
            f"{SERVICENOW_INSTANCE}/api/now/table/sys_db_object"
        )

        params = {
            "sysparm_query": f"nameLIKE{query}^ORlabelLIKE{query}",
            "sysparm_fields": "name,label",
            "sysparm_limit": 100
        }

        response = httpx.get(
            db_object_url,
            headers=headers,
            params=params,
            timeout=30.0
        )

        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=response.text
            )

        data = response.json()

        for table in data.get("result", []):

            name = table.get("name")

            if name:
                table_map[name] = {
                    "name": name,
                    "label": table.get("label") or name
                }

        # =====================================================
        # 2. SEARCH sys_dictionary
        # =====================================================

        dictionary_url = (
            f"{SERVICENOW_INSTANCE}/api/now/table/sys_dictionary"
        )

        params = {
            "sysparm_query": f"nameLIKE{query}",
            "sysparm_fields": "name",
            "sysparm_limit": 500
        }

        response = httpx.get(
            dictionary_url,
            headers=headers,
            params=params,
            timeout=30.0
        )

        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=response.text
            )

        data = response.json()

        for field in data.get("result", []):

            table_name = field.get("name")

            if not table_name:
                continue

            # Add only if not already found
            if table_name not in table_map:

                table_map[table_name] = {
                    "name": table_name,
                    "label": table_name
                }

    except httpx.RequestError as e:

        raise HTTPException(
            status_code=502,
            detail=f"Could not connect to ServiceNow: {str(e)}"
        )

    # Convert dictionary to list
    tables = list(table_map.values())

    # Sort alphabetically
    tables.sort(
        key=lambda table: table["label"].lower()
    )

    return {
        "query": query,
        "count": len(tables),
        "tables": tables
    }

# =========================================================
# DYNAMIC FIELD DISCOVERY
# =========================================================

# =========================================================
# DYNAMIC FIELD DISCOVERY
# =========================================================
# =========================================================
# DYNAMIC FIELD DISCOVERY INCLUDING INHERITED FIELDS
# =========================================================
# =========================================================
# DYNAMIC FIELD DISCOVERY INCLUDING INHERITED FIELDS
# =========================================================

@app.get("/fields/{table_name}")
def get_fields(table_name: str):

    # -----------------------------------------------------
    # Check authentication
    # -----------------------------------------------------

    if not access_token:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated with ServiceNow. Please login first."
        )

    # -----------------------------------------------------
    # Validate table name
    # -----------------------------------------------------

    if not table_name.replace("_", "").isalnum():
        raise HTTPException(
            status_code=400,
            detail="Invalid table name"
        )

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json"
    }

    # field name -> field information
    field_map = {}

    # -----------------------------------------------------
    # Get fields defined directly on one table
    # -----------------------------------------------------

    def get_table_fields(current_table: str):

        url = f"{SERVICENOW_INSTANCE}/api/now/table/sys_dictionary"

        params = {
            "sysparm_query": f"name={current_table}",
            "sysparm_fields": "element,column_label,internal_type",
            "sysparm_limit": 500
        }

        response = httpx.get(
            url,
            headers=headers,
            params=params,
            timeout=30.0
        )

        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=response.text
            )

        data = response.json()

        for field in data.get("result", []):

            element = field.get("element")

            if not element:
                continue

            internal_type = field.get("internal_type")
            column_label = field.get("column_label")

            if isinstance(internal_type, dict):
                internal_type = internal_type.get("value")

            if isinstance(column_label, dict):
                column_label = column_label.get("value")

            # Child fields are added first.
            # Parent fields are added only if the
            # field does not already exist.
            if element not in field_map:

                field_map[element] = {
                    "name": element,
                    "label": column_label or element,
                    "type": internal_type
                }

    # -----------------------------------------------------
    # Find complete table hierarchy
    # -----------------------------------------------------

    current_table = table_name
    visited_tables = set()

    try:

        while current_table:

            # Prevent infinite loops
            if current_table in visited_tables:
                break

            visited_tables.add(current_table)

            # ---------------------------------------------
            # Get fields for current table
            # ---------------------------------------------

            get_table_fields(current_table)

            # ---------------------------------------------
            # Find sys_db_object record
            # ---------------------------------------------

            url = (
                f"{SERVICENOW_INSTANCE}/api/now/table/sys_db_object"
            )

            params = {
                "sysparm_query": f"name={current_table}",
                "sysparm_fields": "sys_id,name,super_class",
                "sysparm_limit": 1
            }

            response = httpx.get(
                url,
                headers=headers,
                params=params,
                timeout=30.0
            )

            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=response.text
                )

            data = response.json()
            results = data.get("result", [])

            if not results:
                break

            super_class = results[0].get("super_class")

            # No parent
            if not super_class:
                break

            # ---------------------------------------------
            # Resolve parent sys_id
            # ---------------------------------------------

            if isinstance(super_class, dict):
                parent_sys_id = super_class.get("value")
            else:
                parent_sys_id = super_class

            if not parent_sys_id:
                break

            # ---------------------------------------------
            # Get parent table name from sys_db_object
            # ---------------------------------------------

            parent_url = (
                f"{SERVICENOW_INSTANCE}/api/now/table/sys_db_object"
                f"/{parent_sys_id}"
            )

            parent_params = {
                "sysparm_fields": "name"
            }

            parent_response = httpx.get(
                parent_url,
                headers=headers,
                params=parent_params,
                timeout=30.0
            )

            if parent_response.status_code != 200:
                raise HTTPException(
                    status_code=parent_response.status_code,
                    detail=parent_response.text
                )

            parent_data = parent_response.json()
            parent_result = parent_data.get("result", {})

            current_table = parent_result.get("name")

            if not current_table:
                break

    except httpx.RequestError as e:

        raise HTTPException(
            status_code=502,
            detail=f"Could not connect to ServiceNow: {str(e)}"
        )

    # -----------------------------------------------------
    # Convert to list
    # -----------------------------------------------------

    fields = list(field_map.values())

    fields.sort(
        key=lambda field: field["label"].lower()
    )

    # -----------------------------------------------------
    # Return
    # -----------------------------------------------------

    return {
        "table": table_name,
        "count": len(fields),
        "fields": fields
    }
# =========================================================
# DYNAMIC TABLE EXPORT WITH FIELD SELECTION
# =========================================================

# =========================================================
# FILTER MODELS
# =========================================================

class FilterCondition(BaseModel):
    field: str
    operator: Literal[
        "is",
        "is_not",
        "contains",
        "starts_with",
        "ends_with",
        "is_empty",
        "is_not_empty"
    ]
    value: str | None = None

class AdvancedExportRequest(BaseModel):
    fields: list[str] | None = None
    filters: list[FilterCondition] = Field(default_factory=list)
    logic: Literal["AND", "OR"] = "AND"
    order_by: str | None = None
    order_direction: Literal["ASC", "DESC"] = "ASC"



# =========================================================
# JSON NORMALIZATION
# =========================================================

def normalize_value(value):
    """
    Convert ServiceNow API field values into clean JSON values.
    """

    if isinstance(value, dict):

        # Prefer display value for ServiceNow reference fields
        if "display_value" in value:
            return value["display_value"]

        # Fallback to raw value
        if "value" in value:
            return value["value"]

        # Recursively normalize any nested object
        return {
            key: normalize_value(item)
            for key, item in value.items()
        }

    if isinstance(value, list):

        return [
            normalize_value(item)
            for item in value
        ]

    return value


def normalize_record(record):
    """
    Normalize every field in one ServiceNow record.
    """

    return {
        field_name: normalize_value(field_value)
        for field_name, field_value in record.items()
    }


# =========================================================
# BUILD SERVICENOW ENCODED QUERY
# =========================================================


def build_encoded_query(
    filters: list[FilterCondition],
    logic: str = "AND"
) -> str:

    operator_map = {
        "is": "=",
        "is_not": "!=",
        "contains": "LIKE",
        "starts_with": "STARTSWITH",
        "ends_with": "ENDSWITH",
        "is_empty": "ISEMPTY",
        "is_not_empty": "ISNOTEMPTY",
    }

    query_parts = []

    for filter_item in filters:

        field = filter_item.field.strip()

        if not field:
            continue

        if not field.replace("_", "").isalnum():
            raise HTTPException(
                status_code=400,
                detail=f"Invalid filter field: {field}"
            )

        operator = operator_map.get(filter_item.operator)

        if not operator:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported filter operator: {filter_item.operator}"
            )

        if filter_item.operator in [
            "is_empty",
            "is_not_empty"
        ]:
            query_parts.append(
                f"{field}{operator}"
            )
            continue

        if filter_item.value is None:
            raise HTTPException(
                status_code=400,
                detail=f"Value is required for field: {field}"
            )

        value = str(filter_item.value).strip()

        query_parts.append(
            f"{field}{operator}{value}"
        )

    if not query_parts:
        return ""

    separator = "^" if logic == "AND" else "^OR"

    return separator.join(query_parts)    

# =========================================================
# DYNAMIC TABLE EXPORT WITH FIELD SELECTION
# =========================================================
@app.get("/export/{table_name}")
def export_table(
    table_name: str,
    fields: str | None = None
):

    # -----------------------------------------------------
    # Check authentication
    # -----------------------------------------------------

    if not access_token:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated with ServiceNow. Please login first."
        )

    # -----------------------------------------------------
    # Validate table name
    # -----------------------------------------------------

    if not table_name.replace("_", "").isalnum():
        raise HTTPException(
            status_code=400,
            detail="Invalid table name"
        )

    # -----------------------------------------------------
    # ServiceNow Table API URL
    # -----------------------------------------------------

    url = f"{SERVICENOW_INSTANCE}/api/now/table/{table_name}"

    # -----------------------------------------------------
    # Convert fields string into a list
    # -----------------------------------------------------

    selected_fields = None

    if fields:

        selected_fields = []

        for field in fields.split(","):

            field = field.strip()

            if not field:
                continue

            # Validate field name
            if not field.replace("_", "").isalnum():
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid field name: {field}"
                )

            # Block sensitive fields
            if is_sensitive_field(field):
                raise HTTPException(
                    status_code=403,
                    detail=f"Export of sensitive field '{field}' is not allowed."
                )

            selected_fields.append(field)



    # -----------------------------------------------------
    # Store all records
    # -----------------------------------------------------

    all_records = []

    # -----------------------------------------------------
    # Pagination settings
    # -----------------------------------------------------

    limit = 100
    offset = 0

    # -----------------------------------------------------
    # Request headers
    # -----------------------------------------------------

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json"
    }

    try:

        while True:

            # -------------------------------------------------
            # Build request parameters
            # -------------------------------------------------

            params = {
                "sysparm_limit": limit,
                "sysparm_offset": offset
            }

            # -------------------------------------------------
            # Add selected fields
            # -------------------------------------------------

            if selected_fields:
                params["sysparm_fields"] = ",".join(
                    selected_fields
                )

            # -------------------------------------------------
            # Call ServiceNow
            # -------------------------------------------------

            response = httpx.get(
                url,
                headers=headers,
                params=params,
                timeout=60.0
            )

            # -------------------------------------------------
            # Handle ServiceNow errors
            # -------------------------------------------------

            if response.status_code != 200:
                handle_servicenow_error(response)

            # -------------------------------------------------
            # Process response
            # -------------------------------------------------

            data = response.json()

            records = data.get("result", [])

            # Add current page records
            all_records.extend(records)

            # -------------------------------------------------
            # Stop when final page is reached
            # -------------------------------------------------

            if len(records) < limit:
                break

            # -------------------------------------------------
            # Move to next page
            # -------------------------------------------------

            offset += limit

    # ---------------------------------------------------------
    # Handle timeout
    # ---------------------------------------------------------

    except httpx.TimeoutException:

        raise HTTPException(
            status_code=504,
            detail="The request to ServiceNow timed out. Please try again."
        )

    # ---------------------------------------------------------
    # Handle connection errors
    # ---------------------------------------------------------

    except httpx.RequestError as e:

        raise HTTPException(
            status_code=502,
            detail=f"Could not connect to ServiceNow: {str(e)}"
        )

    # -----------------------------------------------------
    # Return result
    # -----------------------------------------------------

    return {
        "table": table_name,
        "count": len(all_records),
        "selected_fields": selected_fields,
        "records": all_records
    }

    


    

# =========================================================
# ADVANCED EXPORT WITH FILTERS
# =========================================================
@app.post("/export/{table_name}/advanced")
def advanced_export(
    table_name: str,
    request: AdvancedExportRequest
):

    # -----------------------------------------------------
    # Check authentication
    # -----------------------------------------------------

    if not access_token:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated with ServiceNow. Please login first."
        )

    # -----------------------------------------------------
    # Validate table name
    # -----------------------------------------------------

    if not table_name.replace("_", "").isalnum():
        raise HTTPException(
            status_code=400,
            detail="Invalid table name"
        )

    # -----------------------------------------------------
    # ServiceNow Table API URL
    # -----------------------------------------------------

    url = f"{SERVICENOW_INSTANCE}/api/now/table/{table_name}"

    # -----------------------------------------------------
    # Security validation - Filters
    # -----------------------------------------------------

    for filter_condition in request.filters:

        if is_sensitive_field(filter_condition.field):
            raise HTTPException(
                status_code=403,
                detail=(
                    f"Sensitive field '{filter_condition.field}' "
                    "cannot be used in filters."
                )
            )

    # -----------------------------------------------------
    # Build ServiceNow encoded query
    # -----------------------------------------------------

    encoded_query = build_encoded_query(
        request.filters,
        request.logic
    )

    # -----------------------------------------------------
    # Prepare fields
    # -----------------------------------------------------

    selected_fields = []

    if request.fields:

        for field in request.fields:

            field = field.strip()

            if not field:
                continue

            # Validate field name
            if not field.replace("_", "").isalnum():
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid field name: {field}"
                )

            # Block sensitive fields
            if is_sensitive_field(field):
                raise HTTPException(
                    status_code=403,
                    detail=f"Export of sensitive field '{field}' is not allowed."
                )

            selected_fields.append(field)

    # -----------------------------------------------------
    # Prepare ordering
    # -----------------------------------------------------

    order_by = None

    if request.order_by:

        order_by = request.order_by.strip()

        # Validate order field
        if not order_by.replace("_", "").isalnum():
            raise HTTPException(
                status_code=400,
                detail=f"Invalid order field: {order_by}"
            )

        # Block sensitive fields from sorting
        if is_sensitive_field(order_by):
            raise HTTPException(
                status_code=403,
                detail=(
                    f"Sensitive field '{order_by}' "
                    "cannot be used for sorting."
                )
            )

    # -----------------------------------------------------
    # Pagination
    # -----------------------------------------------------

    limit = 500
    offset = 0

    all_records = []

    # -----------------------------------------------------
    # Request headers
    # -----------------------------------------------------

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json"
    }

    try:

        while True:

            # -------------------------------------------------
            # Build request parameters
            # -------------------------------------------------

            params = {
                "sysparm_limit": limit,
                "sysparm_offset": offset,
                "sysparm_display_value": "all"
            }

            # -------------------------------------------------
            # Add selected fields
            # -------------------------------------------------

            if selected_fields:

                params["sysparm_fields"] = ",".join(
                    selected_fields
                )

            # -------------------------------------------------
            # Build final encoded query
            # -------------------------------------------------

            final_query = encoded_query

            # -------------------------------------------------
            # Add ordering
            # -------------------------------------------------

            if order_by:

                order_expression = (
                    f"ORDERBYDESC{order_by}"
                    if request.order_direction == "DESC"
                    else f"ORDERBY{order_by}"
                )

                if final_query:

                    final_query = (
                        f"{final_query}^{order_expression}"
                    )

                else:

                    final_query = order_expression

            # -------------------------------------------------
            # Add query to request
            # -------------------------------------------------

            if final_query:

                params["sysparm_query"] = final_query

            # -------------------------------------------------
            # Call ServiceNow
            # -------------------------------------------------

            response = httpx.get(
                url,
                headers=headers,
                params=params,
                timeout=60.0
            )

            # -------------------------------------------------
            # Refresh token if expired
            # -------------------------------------------------

            if response.status_code == 401:

                # Get a fresh access token
                refresh_service_now_token()

                # Update Authorization header
                headers["Authorization"] = f"Bearer {access_token}"

                # Retry the same ServiceNow request once
                response = httpx.get(
                    url,
                    headers=headers,
                    params=params,
                    timeout=60.0
                )

            # -------------------------------------------------
            # Handle ServiceNow HTTP errors
            # -------------------------------------------------

            if response.status_code != 200:
                handle_servicenow_error(response)

            # -------------------------------------------------
            # Process current page
            # -------------------------------------------------

            data = response.json()

            records = data.get("result", [])

            # -------------------------------------------------
            # Normalize records
            # -------------------------------------------------

            normalized_records = [
                normalize_record(record)
                for record in records
            ]

            all_records.extend(normalized_records)

            # -------------------------------------------------
            # Stop when final page is reached
            # -------------------------------------------------

            if len(records) < limit:
                break

            # -------------------------------------------------
            # Move to next page
            # -------------------------------------------------

            offset += limit

    # ---------------------------------------------------------
    # Handle timeout
    # ---------------------------------------------------------

    except httpx.TimeoutException:

        raise HTTPException(
            status_code=504,
            detail="The request to ServiceNow timed out. Please try again."
        )

    # ---------------------------------------------------------
    # Handle connection/request errors
    # ---------------------------------------------------------

    except httpx.RequestError as e:

        raise HTTPException(
            status_code=502,
            detail=f"Could not connect to ServiceNow: {str(e)}"
        )

    # -----------------------------------------------------
    # Return advanced export result
    # -----------------------------------------------------

    return {
        "table": table_name,
        "count": len(all_records),
        "selected_fields": selected_fields,
        "filters": [
            {
                "field": item.field,
                "operator": item.operator,
                "value": item.value
            }
            for item in request.filters
        ],
        "logic": request.logic,
        "order_by": order_by,
        "order_direction": request.order_direction,
        "encoded_query": final_query,
        "records": all_records
    }