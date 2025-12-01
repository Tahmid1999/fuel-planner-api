(() => {
    const config = window.fuelPlannerDemoConfig || {};
    const endpoint = config.endpoint;

    const form = document.getElementById("planner-form");
    const startInput = document.getElementById("start-input");
    const finishInput = document.getElementById("finish-input");
    const rangeInput = document.getElementById("range-input");
    const mpgInput = document.getElementById("mpg-input");
    const planButton = document.getElementById("plan-button");
    const statusEl = document.getElementById("status");
    const mapFrame = document.getElementById("map-frame");
    const metricGrid = document.getElementById("metric-grid");
    const stopsContainer = document.getElementById("stops-table");
    const segmentsContainer = document.getElementById("segments-table");
    const cityOptionsList = document.getElementById("city-options");

    let mapUrl;
    let cityLookup = new Map();

    const DEFAULT_CITIES = [
        "Austin, TX",
        "Chicago, IL",
        "Los Angeles, CA",
        "New York, NY",
        "Denver, CO",
        "Seattle, WA",
        "Miami, FL",
        "Phoenix, AZ",
        "Atlanta, GA",
        "Kansas City, MO",
    ];

    const citiesEndpoint = config.citiesEndpoint;

    if (!endpoint) {
        setStatus("API endpoint unavailable.", "error");
        form?.addEventListener("submit", (evt) => evt.preventDefault());
        return;
    }

    init();

    window.addEventListener("beforeunload", () => {
        if (mapUrl) {
            URL.revokeObjectURL(mapUrl);
            mapUrl = null;
        }
    });

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        await fetchPlan();
    });

    async function init() {
        const cities = await loadCities();
        populateCityOptions(cities);
        if (!startInput.value && cities.length > 0) {
            startInput.value = cities[0];
        }
        if (!finishInput.value && cities.length > 1) {
            finishInput.value = cities[1];
        }
        setStatus("Ready to plan a trip.");
    }

    async function loadCities() {
        if (!citiesEndpoint) {
            return DEFAULT_CITIES;
        }
        try {
            const response = await fetch(citiesEndpoint);
            if (!response.ok) {
                throw new Error("Failed to load cities");
            }
            const data = await response.json();
            if (Array.isArray(data.cities) && data.cities.length > 0) {
                return data.cities;
            }
        } catch (error) {
            console.warn("Falling back to default city list:", error);
        }
        return DEFAULT_CITIES;
    }

    function populateCityOptions(cities) {
        if (!cityOptionsList) {
            return;
        }
        cityLookup = new Map();
        cities.forEach((city) => {
            cityLookup.set(normalizeCityValue(city), city);
        });
        cityOptionsList.innerHTML = cities.map((city) => `<option value="${city}"></option>`).join("");
    }

    function normalizeCityValue(value = "") {
        return value
            .trim()
            .replace(/\s+/g, " ")
            .replace(/\s*,\s*/g, ", ")
            .toLowerCase();
    }

    function canonicalizeCity(value) {
        const normalized = normalizeCityValue(value);
        return cityLookup.get(normalized);
    }

    async function fetchPlan() {
        setStatus("Fetching optimal route…");
        setLoading(true);

        const startValue = canonicalizeCity(startInput.value);
        const finishValue = canonicalizeCity(finishInput.value);

        if (!startValue || !finishValue) {
            setStatus("Please pick start and finish from the suggested list.", "error");
            setLoading(false);
            return;
        }

        const payload = {
            start: startValue,
            finish: finishValue,
            vehicle_range_miles: Number(rangeInput.value),
            fuel_efficiency_mpg: Number(mpgInput.value),
        };

        try {
            const response = await fetch(endpoint, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify(payload),
            });

            if (!response.ok) {
                const errorBody = await response.json().catch(() => ({}));
                throw new Error(errorBody.detail || "Unable to plan route.");
            }

            const data = await response.json();
            setStatus("Route ready!");
            updateMetrics(data);
            updateStopsTable(data.fuel_plan?.stops || []);
            updateSegmentsTable(data.fuel_plan?.segments || []);
            updateMap(data.map_html);
        } catch (error) {
            console.error(error);
            setStatus(error.message || "Unexpected error", "error");
        } finally {
            setLoading(false);
        }
    }

    function setLoading(isLoading) {
        planButton.disabled = isLoading;
    }

    function setStatus(message, level = "info") {
        statusEl.textContent = message;
        statusEl.style.color = level === "error" ? "#b91c1c" : "#475569";
    }

    function updateMetrics(data) {
        const route = data.route || {};
        const fuel = data.fuel_plan || {};
        const metrics = [
            { label: "Distance", value: `${route.distance_miles ?? "—"} mi` },
            { label: "Duration", value: `${route.duration_minutes ?? "—"} min` },
            { label: "Fuel Cost", value: fuel.total_cost_usd != null ? `$${fuel.total_cost_usd}` : "—" },
            { label: "Gallons", value: fuel.total_gallons != null ? `${fuel.total_gallons}` : "—" },
        ];

        metricGrid.innerHTML = metrics
            .map(
                (metric) => `
            <div class="metric">
                <span>${metric.label}</span>
                <strong>${metric.value}</strong>
            </div>`
            )
            .join("");
    }

    function updateStopsTable(stops) {
        if (!stops.length) {
            stopsContainer.innerHTML = "<p>No stops returned.</p>";
            return;
        }

        const rows = stops
            .map((stop) => {
                const coords = stop.coordinates || {};
                return `
                <tr>
                    <td>${stop.name}</td>
                    <td>${stop.city}, ${stop.state}</td>
                    <td>${stop.type === "start" ? "Start" : "Refuel"}</td>
                    <td>$${stop.price_per_gallon?.toFixed?.(3) ?? stop.price_per_gallon}</td>
                    <td>${stop.mile_marker?.toFixed?.(1) ?? stop.mile_marker}</td>
                </tr>`;
            })
            .join("");

        stopsContainer.innerHTML = `
            <table>
                <thead>
                    <tr>
                        <th>Name</th>
                        <th>Location</th>
                        <th>Stop type</th>
                        <th>$/gal</th>
                        <th>Mile marker</th>
                    </tr>
                </thead>
                <tbody>${rows}</tbody>
            </table>`;
    }

    function updateSegmentsTable(segments) {
        if (!segments.length) {
            segmentsContainer.innerHTML = "<p>No segments calculated.</p>";
            return;
        }

        const rows = segments
            .map(
                (segment) => `
                <tr>
                    <td>${segment.from_stop}</td>
                    <td>${segment.segment_distance_miles} mi</td>
                    <td>${segment.gallons_used} gal</td>
                    <td>$${segment.cost_usd}</td>
                </tr>`
            )
            .join("");

        segmentsContainer.innerHTML = `
            <table>
                <thead>
                    <tr>
                        <th>From stop</th>
                        <th>Distance</th>
                        <th>Gallons</th>
                        <th>Cost</th>
                    </tr>
                </thead>
                <tbody>${rows}</tbody>
            </table>`;
    }

    function updateMap(mapHtml) {
        if (mapUrl) {
            URL.revokeObjectURL(mapUrl);
            mapUrl = null;
        }

        if (!mapHtml) {
            mapFrame.removeAttribute("src");
            return;
        }

        const blob = new Blob([mapHtml], { type: "text/html" });
        mapUrl = URL.createObjectURL(blob);
        mapFrame.src = mapUrl;
    }
})();

