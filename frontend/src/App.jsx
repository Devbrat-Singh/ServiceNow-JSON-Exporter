import { useEffect, useMemo, useState } from "react";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

const SENSITIVE_FIELD_NAMES = new Set([
  "password",
  "user_password",
  "password_hash",
  "api_key",
  "access_token",
  "refresh_token",
  "client_secret",
  "private_key",
  "secret_key",
]);

const isSensitiveField = (fieldName) => {
  const normalizedName = fieldName.trim().toLowerCase();

  if (SENSITIVE_FIELD_NAMES.has(normalizedName)) {
    return true;
  }

  const sensitivePatterns = [
    "password",
    "client_secret",
    "private_key",
    "access_token",
    "refresh_token",
  ];

  return sensitivePatterns.some((pattern) => normalizedName.includes(pattern));
};

function App() {
  // ==================================================
  // TABLE STATE
  // ==================================================

  const [tables, setTables] = useState([]);
  const [selectedTable, setSelectedTable] = useState("");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [searching, setSearching] = useState(false);

  // ==================================================
  // FIELD STATE
  // ==================================================

  const [fields, setFields] = useState([]);
  const [selectedFields, setSelectedFields] = useState([]);
  const [fieldSearch, setFieldSearch] = useState("");
  const [loadingFields, setLoadingFields] = useState(false);
  const [filters, setFilters] = useState([]);
  const [filterLogic, setFilterLogic] = useState("AND");
  const [filterFieldSearch, setFilterFieldSearch] = useState("");
  const [sortField, setSortField] = useState("");
  const [sortDirection, setSortDirection] = useState("ASC");

  // ==================================================
  // EXPORT STATE
  // ==================================================

  const [exporting, setExporting] = useState(false);
  const [exportData, setExportData] = useState(null);

  // ==================================================
  // GENERAL STATE
  // ==================================================

  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);

  // ==================================================
  // LOAD ALL TABLES
  // ==================================================

  const loadAllTables = async () => {
    try {
      setLoading(true);
      setError("");

      const response = await fetch(`${API_BASE_URL}/tables`);

      if (!response.ok) {
        throw new Error("Failed to load ServiceNow tables");
      }

      const data = await response.json();

      setTables(data.tables || []);
    } catch (error) {
      setError(error.message);
    } finally {
      setLoading(false);
    }
  };

  // ==================================================
  // INITIAL LOAD
  // ==================================================

  useEffect(() => {
    loadAllTables();
  }, []);

  // ==================================================
  // SEARCH TABLES
  // ==================================================

  useEffect(() => {
    const query = search.trim();

    if (!query) {
      loadAllTables();
      return;
    }

    setSearching(true);
    setError("");

    const timer = setTimeout(async () => {
      try {
        const response = await fetch(
          `${API_BASE_URL}/tables/search?query=${encodeURIComponent(query)}`,
        );

        if (!response.ok) {
          throw new Error("Table search failed");
        }

        const data = await response.json();

        setTables(data.tables || []);
      } catch (error) {
        setError(error.message);
        setTables([]);
      } finally {
        setSearching(false);
      }
    }, 350);

    return () => clearTimeout(timer);
  }, [search]);

  // ==================================================
  // LOAD FIELDS FOR SELECTED TABLE
  // ==================================================

  const loadFields = async (tableName) => {
    try {
      setLoadingFields(true);
      setError("");

      const response = await fetch(
        `${API_BASE_URL}/fields/${encodeURIComponent(tableName)}`,
      );

      if (!response.ok) {
        throw new Error("Failed to load table fields");
      }

      const data = await response.json();

      setFields(data.fields || []);

      // Start with no fields selected.
      setSelectedFields([]);
    } catch (error) {
      setFields([]);
      setSelectedFields([]);
      setError(error.message);
    } finally {
      setLoadingFields(false);
    }
  };

  // ==================================================
  // HANDLE TABLE SELECTION
  // ==================================================

  const handleTableChange = async (event) => {
    const tableName = event.target.value;

    setSelectedTable(tableName);

    setExportData(null);
    setSelectedFields([]);
    setFields([]);
    setFieldSearch("");
    setFilters([]);
    setFilterLogic("AND");
    setFilterFieldSearch("");
    setError("");
    setCopied(false);
    setSortField("");
    setSortDirection("ASC");

    if (tableName) {
      await loadFields(tableName);
    }
  };

  // ==================================================
  // FILTER VISIBLE FIELDS
  // ==================================================

  const filteredFields = useMemo(() => {
    const query = fieldSearch.toLowerCase().trim();

    if (!query) {
      return fields;
    }

    return fields.filter((field) =>
      `${field.name} ${field.label} ${field.type}`
        .toLowerCase()
        .includes(query),
    );
  }, [fields, fieldSearch]);

  const filteredFilterFields = useMemo(() => {
    const query = filterFieldSearch.toLowerCase().trim();

    if (!query) {
      return fields;
    }

    return fields.filter((field) =>
      `${field.name} ${field.label} ${field.type}`
        .toLowerCase()
        .includes(query),
    );
  }, [fields, filterFieldSearch]);

  // ==================================================
  // TOGGLE FIELD
  // ==================================================
  const toggleField = (fieldName) => {
    if (isSensitiveField(fieldName)) {
      return;
    }

    setSelectedFields((current) => {
      if (current.includes(fieldName)) {
        return current.filter((name) => name !== fieldName);
      }

      return [...current, fieldName];
    });

    setExportData(null);
    setError("");
  };

  // ==================================================
  // SELECT ALL VISIBLE FIELDS
  // ==================================================

  const handleSelectAll = () => {
    const visibleFieldNames = filteredFields
      .filter((field) => !isSensitiveField(field.name))
      .map((field) => field.name);

    setSelectedFields((current) => {
      const combined = new Set([...current, ...visibleFieldNames]);

      return Array.from(combined);
    });
  };

  // ==================================================
  // CLEAR ALL FIELDS
  // ==================================================

  const handleClearAll = () => {
    setSelectedFields([]);
    setExportData(null);
  };

  const addFilter = () => {
    setFilters((currentFilters) => [
      ...currentFilters,
      {
        field: "",
        operator: "is",
        value: "",
      },
    ]);
  };

  const removeFilter = (index) => {
    setFilters((currentFilters) =>
      currentFilters.filter((_, filterIndex) => filterIndex !== index),
    );
  };

  const updateFilter = (index, key, value) => {
    setFilters((currentFilters) =>
      currentFilters.map((filter, filterIndex) =>
        filterIndex === index
          ? {
              ...filter,
              [key]: value,
            }
          : filter,
      ),
    );
  };

  // ==================================================
  // EXPORT TABLE
  // ==================================================

  const handleExport = async () => {
    if (!selectedTable) {
      setError("Please select a table first.");
      return;
    }

    if (selectedFields.length === 0) {
      setError("Please select at least one field to export.");
      return;
    }

    // Validate filters
    for (const filter of filters) {
      if (!filter.field) {
        setError("Please select a field for every filter condition.");
        return;
      }

      if (
        filter.operator !== "is_empty" &&
        filter.operator !== "is_not_empty" &&
        !filter.value.trim()
      ) {
        setError(`Please enter a value for "${filter.field}".`);
        return;
      }
    }

    try {
      setExporting(true);
      setError("");
      setExportData(null);
      setCopied(false);

      const requestBody = {
        fields: selectedFields,

        filters: filters.map((filter) => ({
          field: filter.field,
          operator: filter.operator,
          value:
            filter.operator === "is_empty" || filter.operator === "is_not_empty"
              ? null
              : filter.value,
        })),

        logic: filterLogic,

        order_by: sortField || null,
        order_direction: sortDirection,
      };

      const response = await fetch(
        `${API_BASE_URL}/export/${encodeURIComponent(selectedTable)}/advanced`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(requestBody),
        },
      );

      if (!response.ok) {
        const errorData = await response.json().catch(() => null);

        throw new Error(errorData?.detail || "Failed to export table");
      }

      const data = await response.json();

      setExportData(data);
    } catch (error) {
      setError(error.message);
    } finally {
      setExporting(false);
    }
  };

  // ==================================================
  // COPY JSON
  // ==================================================

  const handleCopy = async () => {
    if (!exportData) {
      return;
    }

    try {
      const jsonString = JSON.stringify(exportData, null, 2);

      await navigator.clipboard.writeText(jsonString);

      setCopied(true);

      setTimeout(() => {
        setCopied(false);
      }, 2000);
    } catch {
      setError("Unable to copy JSON to clipboard.");
    }
  };

  // ==================================================
  // DOWNLOAD JSON
  // ==================================================

  const handleDownload = () => {
    if (!exportData) {
      return;
    }

    const jsonString = JSON.stringify(exportData, null, 2);

    const blob = new Blob([jsonString], {
      type: "application/json",
    });

    const url = URL.createObjectURL(blob);

    const link = document.createElement("a");

    link.href = url;
    link.download = `${selectedTable}.json`;

    document.body.appendChild(link);

    link.click();

    document.body.removeChild(link);

    URL.revokeObjectURL(url);
  };

  // ==================================================
  // CLEAR TABLE SEARCH
  // ==================================================

  const clearSearch = () => {
    setSearch("");
    setSelectedTable("");
    setFields([]);
    setSelectedFields([]);
    setFieldSearch("");
    setFilters([]);
    setFilterLogic("AND");
    setFilterFieldSearch("");
    setSortField("");
    setSortDirection("ASC");
    setExportData(null);
    setError("");
  };

  // ==================================================
  // UI
  // ==================================================

  return (
    <div className="app">
      {/* ==============================================
          HEADER
      ============================================== */}

      <header className="app-header">
        <div className="brand">
          <div className="brand-icon">SN</div>

          <div>
            <h1>ServiceNow JSON Data Exporter</h1>

            <p>Dynamically export ServiceNow table data as JSON</p>
          </div>
        </div>

        <div className="connection-status">
          <span className="status-dot"></span>
          ServiceNow Connected
        </div>
      </header>

      {/* ==============================================
          MAIN
      ============================================== */}

      <main className="main-content">
        {/* ============================================
            TABLE SELECTION
        ============================================ */}

        <section className="card">
          <div className="section-header">
            <div>
              <h2>Select ServiceNow Table</h2>

              <p>Search for an accessible ServiceNow table</p>
            </div>

            <div className="table-header-actions">
              <div className="table-count-badge">
                {searching ? "Searching..." : `${tables.length} tables`}
              </div>

              <button
                type="button"
                className="refresh-button"
                onClick={loadAllTables}
                disabled={loading || searching}
                title="Refresh ServiceNow tables"
              >
                ↻ Refresh
              </button>
            </div>
          </div>

          {/* Table Search */}

          <div className="table-search">
            <span className="search-icon">🔍</span>

            <input
              type="text"
              placeholder="Search tables... e.g. incident, task, sys_user"
              value={search}
              onChange={(event) => {
                setSearch(event.target.value);
                setSelectedTable("");
                setFields([]);
                setSelectedFields([]);
                setFieldSearch("");
                setExportData(null);
              }}
            />

            {search && (
              <button
                className="clear-search"
                type="button"
                onClick={clearSearch}
              >
                ×
              </button>
            )}
          </div>

          {/* Search info */}

          <div className="search-info">
            {search ? (
              <span>
                Search results for <strong>"{search}"</strong>
              </span>
            ) : (
              <span>Showing available ServiceNow tables</span>
            )}
          </div>

          {/* Table Selector */}

          <div className="table-selector">
            <select
              value={selectedTable}
              onChange={handleTableChange}
              disabled={loading || searching}
            >
              <option value="">Select a table</option>

              {tables.map((table) => (
                <option key={table.name} value={table.name}>
                  {table.label} ({table.name})
                </option>
              ))}
            </select>
          </div>

          {/* Loading Tables */}

          {loading && (
            <div className="loading-state">
              <div className="spinner"></div>

              <span>Loading ServiceNow tables...</span>
            </div>
          )}
        </section>

        {/* ============================================
            FIELD SELECTION
        ============================================ */}

        {selectedTable && (
          <section className="card">
            <div className="section-header">
              <div>
                <h2>Select Fields</h2>

                <p>
                  Choose which fields should be included in the JSON export.
                </p>
              </div>

              <div className="field-header-actions">
                <div className="table-count-badge">
                  {selectedFields.length} selected
                </div>

                <button
                  type="button"
                  className="primary-button header-export-button"
                  onClick={handleExport}
                  disabled={
                    !selectedTable ||
                    selectedFields.length === 0 ||
                    exporting ||
                    loadingFields
                  }
                >
                  {exporting ? (
                    <>
                      <span className="button-spinner"></span>
                      Exporting...
                    </>
                  ) : (
                    <>
                      <span>📤</span>
                      Export JSON
                    </>
                  )}
                </button>
              </div>
            </div>

            {loadingFields ? (
              <div className="loading-state">
                <div className="spinner"></div>

                <span>
                  Loading fields for <strong>{selectedTable}</strong>
                  ...
                </span>
              </div>
            ) : fields.length > 0 ? (
              <>
                {/* Field Search */}

                <div className="table-search">
                  <span className="search-icon">🔍</span>

                  <input
                    type="text"
                    placeholder="Search fields..."
                    value={fieldSearch}
                    onChange={(event) => {
                      setFieldSearch(event.target.value);
                    }}
                  />
                </div>

                {/* Field Controls */}

                <div className="field-controls">
                  <span>
                    Showing <strong>{filteredFields.length}</strong> of{" "}
                    <strong>{fields.length}</strong> fields
                  </span>

                  <div>
                    <button
                      type="button"
                      className="small-button"
                      onClick={handleSelectAll}
                    >
                      Select All
                    </button>

                    <button
                      type="button"
                      className="small-button"
                      onClick={handleClearAll}
                    >
                      Clear All
                    </button>
                  </div>
                </div>

                <div className="field-security-info">
                  🔒 Sensitive fields are protected and cannot be exported.
                </div>

                {/* Fields */}

                {filteredFields.length > 0 ? (
                  <div className="fields-grid">
                    {filteredFields.map((field) => {
                      const isSelected = selectedFields.includes(field.name);
                      const isSensitive = isSensitiveField(field.name);

                      return (
                        <label
                          key={field.name}
                          className={`field-item ${
                            isSelected ? "field-item-selected" : ""
                          }`}
                        >
                          <input
                            type="checkbox"
                            checked={isSelected}
                            disabled={isSensitive}
                            onChange={() => {
                              if (!isSensitive) {
                                toggleField(field.name);
                              }
                            }}
                          />

                          <div className="field-info">
                            <strong>{field.label || field.name}</strong>

                            <span>{field.name}</span>
                          </div>

                          <div className="field-meta">
                            {isSensitive && (
                              <span className="protected-badge">
                                🔒 Protected
                              </span>
                            )}

                            <span className="field-type">
                              {typeof field.type === "object"
                                ? field.type?.value
                                : field.type}
                            </span>
                          </div>
                        </label>
                      );
                    })}
                  </div>
                ) : (
                  <div className="empty-state">
                    <div className="empty-icon">🔎</div>

                    <h3>No fields found</h3>

                    <p>Try another field name.</p>
                  </div>
                )}
              </>
            ) : (
              <div className="empty-state">
                <div className="empty-icon">⚠</div>

                <h3>No fields available</h3>

                <p>No fields were returned for this table.</p>
              </div>
            )}

            {/* Export */}
          </section>
        )}

        {/* ============================================
    FILTER BUILDER
============================================ */}

        {selectedTable && (
          <section className="card">
            <div className="section-header">
              <div>
                <h2>Filters</h2>
                <p>
                  Filter which records should be included in the JSON export.
                </p>
              </div>

              <div className="table-count-badge">
                {filters.length} condition{filters.length !== 1 ? "s" : ""}
              </div>
            </div>

            {/* Logic Selector */}

            {filters.length > 1 && (
              <div className="filter-logic">
                <span>Match conditions using:</span>

                <select
                  value={filterLogic}
                  onChange={(event) => setFilterLogic(event.target.value)}
                >
                  <option value="AND">AND</option>
                  <option value="OR">OR</option>
                </select>
              </div>
            )}

            {/* Filter Conditions */}

            {/* Filter Field Search */}

            <div className="table-search filter-field-search">
              <span className="search-icon">🔍</span>

              <input
                type="text"
                placeholder="Search filter fields... e.g. short_description, priority, state"
                value={filterFieldSearch}
                onChange={(event) => setFilterFieldSearch(event.target.value)}
              />

              {filterFieldSearch && (
                <button
                  className="clear-search"
                  type="button"
                  onClick={() => setFilterFieldSearch("")}
                >
                  ×
                </button>
              )}
            </div>

            <div className="filters-container">
              {filters.length === 0 ? (
                <div className="filter-empty-state">
                  <div className="filter-empty-icon">⚙</div>
                  <div>
                    <strong>No filters configured</strong>
                    <p>
                      All accessible records will be included in the export. Add
                      a condition to limit the results.
                    </p>
                  </div>
                </div>
              ) : (
                filters.map((filter, index) => (
                  <div className="filter-row" key={index}>
                    {/* Field */}

                    <div className="filter-field">
                      <label>Field</label>

                      <select
                        value={filter.field}
                        onChange={(event) =>
                          updateFilter(index, "field", event.target.value)
                        }
                      >
                        <option value="">Select field</option>

                        {filteredFilterFields.map((field) => (
                          <option key={field.name} value={field.name}>
                            {field.label || field.name}
                          </option>
                        ))}
                      </select>
                    </div>

                    {/* Operator */}

                    <div className="filter-field">
                      <label>Operator</label>

                      <select
                        value={filter.operator}
                        onChange={(event) =>
                          updateFilter(index, "operator", event.target.value)
                        }
                      >
                        <option value="is">is</option>
                        <option value="is_not">is not</option>
                        <option value="contains">contains</option>
                        <option value="starts_with">starts with</option>
                        <option value="ends_with">ends with</option>
                        <option value="is_empty">is empty</option>
                        <option value="is_not_empty">is not empty</option>
                      </select>
                    </div>

                    {/* Value */}

                    <div className="filter-field">
                      <label>Value</label>

                      <input
                        type="text"
                        placeholder="Enter value..."
                        value={filter.value}
                        disabled={
                          filter.operator === "is_empty" ||
                          filter.operator === "is_not_empty"
                        }
                        onChange={(event) =>
                          updateFilter(index, "value", event.target.value)
                        }
                      />
                    </div>

                    {/* Remove */}

                    <button
                      type="button"
                      className="remove-filter-button"
                      onClick={() => removeFilter(index)}
                      title="Remove condition"
                    >
                      ×
                    </button>
                  </div>
                ))
              )}
            </div>

            {/* Add Condition */}

            <div className="filter-actions">
              <button
                type="button"
                className="small-button"
                onClick={addFilter}
              >
                + Add Condition
              </button>

              {filters.length > 0 && (
                <button
                  type="button"
                  className="small-button"
                  onClick={() => setFilters([])}
                >
                  Clear Filters
                </button>
              )}
            </div>
          </section>
        )}

        {/* ============================================
    SORTING
============================================ */}
        {selectedTable && (
          <section className="card sorting-card">
            <div className="section-header">
              <div>
                <h2>Sorting</h2>
                <p>Choose how the exported records should be ordered.</p>
              </div>

              <div className="table-count-badge">
                {sortField ? "Sorting enabled" : "No sorting"}
              </div>
            </div>

            <div className="filter-row sorting-row">
              {/* Sort Field */}

              <div className="filter-field">
                <label>Sort Field</label>

                <select
                  value={sortField}
                  onChange={(event) => setSortField(event.target.value)}
                >
                  <option value="">No sorting</option>

                  {fields.map((field) => (
                    <option key={field.name} value={field.name}>
                      {field.label || field.name}
                    </option>
                  ))}
                </select>
              </div>

              {/* Sort Direction */}

              <div className="filter-field">
                <label>Direction</label>

                <select
                  value={sortDirection}
                  onChange={(event) => setSortDirection(event.target.value)}
                  disabled={!sortField}
                >
                  <option value="ASC">Ascending</option>
                  <option value="DESC">Descending</option>
                </select>
              </div>
            </div>
          </section>
        )}

        {/* ============================================
    EXPORT CONFIGURATION SUMMARY
============================================ */}

        {selectedTable && selectedFields.length > 0 && (
          <section className="card export-summary-card">
            <div className="section-header">
              <div>
                <h2>Export Configuration</h2>
                <p>Review your export settings before downloading the JSON.</p>
              </div>
            </div>

            <div className="export-summary-grid">
              <div className="summary-item">
                <span className="summary-label">TABLE</span>
                <strong>{selectedTable}</strong>
              </div>

              <div className="summary-item">
                <span className="summary-label">FIELDS</span>
                <strong>{selectedFields.length}</strong>
              </div>

              <div className="summary-item">
                <span className="summary-label">FILTERS</span>
                <strong>
                  {filters.length === 0
                    ? "None"
                    : `${filters.length} condition${filters.length !== 1 ? "s" : ""}`}
                </strong>
              </div>

              <div className="summary-item">
                <span className="summary-label">SORTING</span>
                <strong>
                  {sortField ? `${sortField} (${sortDirection})` : "None"}
                </strong>
              </div>

              <div className="summary-item">
                <span className="summary-label">FILTER LOGIC</span>
                <strong>{filters.length > 1 ? filterLogic : "N/A"}</strong>
              </div>
            </div>
          </section>
        )}

        {/* ============================================
            ERROR
        ============================================ */}

        {error && (
          <div className="error-message">
            <span className="error-icon">⚠</span>

            <div>
              <strong>Something went wrong</strong>

              <p>{error}</p>
            </div>
          </div>
        )}

        {/* ============================================
            EXPORT RESULT
        ============================================ */}
        {exportData && (
          <section className="card result-card">
            <div className="section-header">
              <div>
                <h2>Export Result</h2>
                <p>JSON data retrieved from ServiceNow</p>
              </div>

              <div className="result-status-group">
                <div className="success-badge">✓ Export Successful</div>

                <div className="json-ready-badge">JSON Ready</div>
              </div>
            </div>

            {/* Stats */}

            <div className="result-stats">
              <div className="stat-box">
                <span className="stat-label">TABLE</span>
                <strong>{exportData.table}</strong>
              </div>

              <div className="stat-box">
                <span className="stat-label">RECORDS</span>
                <strong>{exportData.count}</strong>
              </div>

              <div className="stat-box">
                <span className="stat-label">FIELDS</span>
                <strong>
                  {exportData.selected_fields?.length || selectedFields.length}
                </strong>
              </div>
            </div>

            {/* Actions */}

            <div className="json-actions">
              <button className="secondary-button" onClick={handleCopy}>
                {copied ? "✓ Copied" : "📋 Copy JSON"}
              </button>

              <button className="secondary-button" onClick={handleDownload}>
                ⬇ Download JSON
              </button>
            </div>

            {/* JSON Preview */}

            <div className="json-container">
              <div className="json-header">
                <span>JSON Preview</span>
                <span>{exportData.count} records</span>
              </div>

              <pre>
                {JSON.stringify(
                  {
                    ...exportData,
                    records: exportData.records?.slice(0, 100) || [],
                  },
                  null,
                  2,
                )}
              </pre>

              {exportData.count > 100 && (
                <div className="preview-info">
                  Showing first 100 of {exportData.count} records. Use Download
                  JSON to export the complete dataset.
                </div>
              )}
            </div>
          </section>
        )}
      </main>

      {/* ==============================================
          FOOTER
      ============================================== */}

      <footer className="app-footer">
        <span>ServiceNow JSON Data Exporter</span>

        <span>OAuth 2.0 • FastAPI • React</span>
      </footer>
    </div>
  );
}

export default App;
