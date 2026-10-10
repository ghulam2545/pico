// uses $ and API from app.js, PICO from the template
const USER_ID = "web";
let convoId = location.hash.slice(1);
let busy = false;

const headers = (extra = {}) => ({"X-API-Key": PICO.key, ...extra});
const json = (method, body) => ({
    method, headers: headers({"Content-Type": "application/json"}), body: JSON.stringify(body),
});
const fail = (text) => {
    $("msg").textContent = text;
};

async function call(path, options) {
    const res = await fetch(`${PICO.api}${path}`, options);
    if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(typeof data.detail === "string" ? data.detail : `Error ${res.status}`);
    }
    return res;
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
    document.querySelectorAll("#convos li[data-id]").forEach((li) => {
        li.classList.toggle("active", li.dataset.id === convoId);
    });
}

function openConvo(id) {
    convoId = id;
    location.hash = id;
    $("messages").innerHTML = "";
    markActive();
}

async function newConvo() {
    const res = await call("/conversations", json("POST", {user_id: USER_ID}));
    const c = await res.json();
    location.hash = c.id;
    location.reload();
}

// ---- conversations ----
$("new-convo").onclick = () => newConvo().catch((e) => fail(e.message));

$("convos").onclick = async (e) => {
    const li = e.target.closest("li[data-id]");
    if (!li) return;
    if (e.target.classList.contains("del")) {
        await call(`/conversations/${li.dataset.id}`, {
            method: "DELETE",
            headers: headers()
        }).catch((e) => fail(e.message));
        if (li.dataset.id === convoId) location.hash = "";
        location.reload();
    } else {
        openConvo(li.dataset.id);
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
    try {
        await call("/ingest/upload", {method: "POST", headers: headers(), body: form});
        location.reload();
    } catch (err) {
        fail(err.message);
        btn.disabled = false;
        btn.textContent = "Upload";
    }
};

$("docs").onclick = async (e) => {
    const li = e.target.closest("li[data-id]");
    if (!li || !e.target.classList.contains("del")) return;
    await call(`/documents/${li.dataset.id}`, {method: "DELETE", headers: headers()}).catch((e) => fail(e.message));
    location.reload();
};

// ---- chat ----
async function ensureConvo(title) {
    if (convoId) return;
    const res = await call("/conversations", json("POST", {user_id: USER_ID, name: title.slice(0, 40)}));
    const c = await res.json();
    convoId = c.id;
    location.hash = c.id;
    const li = document.createElement("li");
    li.dataset.id = c.id;
    li.innerHTML = '<span class="name"></span><button class="del" title="Delete">&times;</button>';
    li.querySelector(".name").textContent = c.name;
    const list = $("convos");
    list.querySelector("li:not([data-id])")?.remove();
    list.prepend(li);
    markActive();
}

// SSE: "data: {token}" ... "data: [SOURCES][...]" ... "data: [DONE]"
async function streamAnswer(query, bubble) {
    const filename = $("doc-filter").value;
    const body = {conversation_id: convoId, query, user_id: USER_ID};
    if (filename) body.document_filter = {user_id: USER_ID, filename};

    const res = await call("/chat", json("POST", body));
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
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
            bubble.firstChild.textContent += msg.token;
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
    bubble.prepend(document.createTextNode(""));

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

markActive();

$("logout").onclick = (e) => {
    e.preventDefault();
    document.cookie = "pico_api_key=; path=/; max-age=0";
    location.href = "/";
};