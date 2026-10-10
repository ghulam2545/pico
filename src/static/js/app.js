const $ = (name) => document.getElementById(name);
const API = "/pico/api";

function setCookie(key) {
    document.cookie = `pico_api_key=${encodeURIComponent(key)}; path=/; max-age=2592000; SameSite=Lax`;
}

// ---- landing page ----
if ($("enter-form")) {
    $("enter-form").onsubmit = (e) => {
        e.preventDefault();
        setCookie($("enter-key").value.trim());
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
        setCookie(data.api_key);
        $("created-key").textContent = data.api_key;
        $("created-link").href = `/ws/${data.identifier}`;
        $("created").hidden = false;
    };
}