// uses $, API, KEY from app.js
const USER_ID = "web";
const IDENTIFIER = location.pathname.split("/").pop();
const apiKey = localStorage.getItem(KEY);
const SERVICES = {postgres: "Postgres", redis: "Redis", ollama_local: "Ollama local", ollama_cloud: "Ollama cloud"};
let convoId = location.hash.slice(1);
let busy = false;

function logout(reason) {
    localStorage.removeItem(KEY);
    if (reason) sessionStorage.setItem("pico_msg", reason);
    location.href = "/";
}

if (!apiKey) logout();

const headers = (extra = {}) => ({"X-API-Key": apiKey, ...extra});
const json = (method, body) => ({
    method, headers: headers({"Content-Type": "application/json"}), body: JSON.stringify(body),
});
const fail = (text) => {
    $("msg").textContent = text;
};

async function call(path, options = {headers: headers()}) {
    const res = await fetch(`${API}${path}`, options);
    if (res.status === 401) logout("Invalid API key for this workspace.");
    if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(typeof data.detail === "string" ? data.detail : `Error ${res.status}`);
    }
    return res;
}

// ---- health ----
async function loadHealth() {
    $("health").innerHTML = "";
    try {
        const data = await (await fetch(`${API}/health`)).json();
        for (const [key, label] of Object.entries(SERVICES)) {
            const span = document.createElement("span");
            span.className = `hc ${data[key] === "up" ? "up" : "down"}`;
            span.textContent = label;
            span.title = data[key];
            $("health").appendChild(span);
        }
    } catch (err) { /* ignore */
    }
}

// ---- rendering ----
function addItem(list, id, label, sub) {
    const li = document.createElement("li");
    li.dataset.id = id;
    const name = document.createElement("span");
    name.className = "name";
    name.textContent = label;
    if (sub) {
        const small = document.createElement("small");
        small.textContent = sub;
        name.appendChild(small);
    }
    const del = document.createElement("button");
    del.className = "del";
    del.title = "Delete";
    del.textContent = "×";
    li.append(name, del);
    list.appendChild(li);
    return li;
}

function addMessage(text, cls) {
    const div = document.createElement("div");
    div.className = `msg ${cls}`;
    div.textContent = text;
    $("messages").appendChild(div);
    $("messages").scrollTop = $("messages").scrollHeight;
    return div;
}

function markActive() {
    document.querySelectorAll("#convos li").forEach((li) => {
        li.classList.toggle("active", li.dataset.id === convoId);
    });
}

async function loadConvos() {
    const convos = await (await call(`/conversations?user_id=${USER_ID}`)).json();
    $("convos").innerHTML = "";
    convos.forEach((c) => addItem($("convos"), c.id, c.name));
    markActive();
}

async function loadDocs() {
    const data = await (await call("/documents?size=100")).json();
    $("docs").innerHTML = "";
    $("doc-filter").length = 1;
    data.files.forEach((d) => {
        addItem($("docs"), d.id, d.filename, `${d.chunk_count} chunks`);
        $("doc-filter").add(new Option(d.filename, d.filename));
    });
}

async function init() {
    try {
        const all = await (await call("/workspaces")).json();
        const ws = all.find((w) => w.identifier === IDENTIFIER);
        if (ws) {
            $("ws-name").textContent = `Pico · ${ws.name}`;
            document.title = `Pico · ${ws.name}`;
        }
        await Promise.all([loadConvos(), loadDocs()]);
    } catch (err) {
        fail(err.message);
    }
}

// ---- conversations ----
function openConvo(id) {
    convoId = id;
    location.hash = id;
    $("messages").innerHTML = "";
    markActive();
}

$("new-convo").onclick = async () => {
    try {
        const c = await (await call("/conversations", json("POST", {user_id: USER_ID}))).json();
        await loadConvos();
        openConvo(c.id);
    } catch (err) {
        fail(err.message);
    }
};

$("convos").onclick = async (e) => {
    const li = e.target.closest("li");
    if (!li) return;
    if (!e.target.classList.contains("del")) return openConvo(li.dataset.id);
    try {
        await call(`/conversations/${li.dataset.id}`, {method: "DELETE", headers: headers()});
        if (li.dataset.id === convoId) openConvo("");
        await loadConvos();
    } catch (err) {
        fail(err.message);
    }
};

// ---- documents ----
$("upload-form").onsubmit = async (e) => {
    e.preventDefault();
    const form = new FormData();
    form.append("file", $("file").files[0]);
    form.append("user_id", USER_ID);
    const btn = e.target.querySelector("button");
    btn.disabled = true;
    btn.textContent = "Uploading...";
    fail("");
    try {
        await call("/ingest/upload", {method: "POST", headers: headers(), body: form});
        e.target.reset();
        await loadDocs();
    } catch (err) {
        fail(err.message);
    }
    btn.disabled = false;
    btn.textContent = "Upload";
};

$("docs").onclick = async (e) => {
    const li = e.target.closest("li");
    if (!li || !e.target.classList.contains("del")) return;
    try {
        await call(`/documents/${li.dataset.id}`, {method: "DELETE", headers: headers()});
        await loadDocs();
    } catch (err) {
        fail(err.message);
    }
};

// ---- chat ----
async function ensureConvo(title) {
    if (convoId) return;
    const c = await (await call("/conversations", json("POST", {user_id: USER_ID, name: title.slice(0, 40)}))).json();
    convoId = c.id;
    location.hash = c.id;
    await loadConvos();
}

// SSE: "data: {token}" ... "data: [SOURCES][...]" ... "data: [DONE]"
async function streamAnswer(query, bubble) {
    const filename = $("doc-filter").value;
    const body = {conversation_id: convoId, query, user_id: USER_ID};
    if (filename) body.document_filter = {user_id: USER_ID, filename};

    const res = await call("/chat", json("POST", body));
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    const text = document.createTextNode("");
    bubble.prepend(text);
    let buffer = "";

    while (true) {
        const {value, done} = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, {stream: true});
        const events = buffer.split("\n\n");
        buffer = events.pop();

        for (const ev of events) {
            const data = ev.replace(/^data: /, "");
            if (data === "[DONE]") return;
            if (data.startsWith("[SOURCES]")) {
                const names = [...new Set(JSON.parse(data.slice(9)).map((s) => s.filename))];
                if (names.length) {
                    const small = document.createElement("small");
                    small.textContent = "Sources: " + names.join(", ");
                    bubble.appendChild(small);
                }
                continue;
            }
            const msg = JSON.parse(data);
            if (msg.error) throw new Error(msg.error);
            text.data += msg.token;
            $("messages").scrollTop = $("messages").scrollHeight;
        }
    }
}

$("chat-form").onsubmit = async (e) => {
    e.preventDefault();
    const query = $("query").value.trim();
    if (!query || busy) return;

    busy = true;
    $("send").disabled = true;
    $("query").value = "";
    fail("");
    addMessage(query, "user");
    const bubble = addMessage("", "bot");

    try {
        await ensureConvo(query);
        await streamAnswer(query, bubble);
    } catch (err) {
        fail(err.message);
    }
    busy = false;
    $("send").disabled = false;
    $("query").focus();
};

$("logout").onclick = (e) => {
    e.preventDefault();
    logout();
};

loadHealth();
setInterval(loadHealth, 150000);
init();
