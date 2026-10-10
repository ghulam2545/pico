const $ = (name) => document.getElementById(name);
const API = "/pico/api";
const KEY = "pico_api_key";

// ---- landing page ----
if ($("enter-form")) {
    $("msg").textContent = sessionStorage.getItem("pico_msg") || "";
    sessionStorage.removeItem("pico_msg");

    $("enter-form").onsubmit = (e) => {
        e.preventDefault();
        localStorage.setItem(KEY, $("enter-key").value.trim());
        location.href = `/ws/${$("enter-identifier").value.trim()}`;
    };

    $("create-form").onsubmit = async (e) => {
        e.preventDefault();
        $("msg").textContent = "";
        const res = await fetch(`${API}/workspaces`, {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({name: $("create-name").value, identifier: $("create-identifier").value}),
        });
        const data = await res.json();
        if (!res.ok) {
            $("msg").textContent = typeof data.detail === "string" ? data.detail : "Invalid input";
            return;
        }
        localStorage.setItem(KEY, data.api_key);
        $("created-key").textContent = data.api_key;
        $("created-link").href = `/ws/${data.identifier}`;
        $("created").hidden = false;
    };
}
