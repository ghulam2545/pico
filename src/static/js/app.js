const $ = (name) => document.getElementById(name);

$("text").onmouseover = () => {
    alert("You hovered the mouse on text.");
};