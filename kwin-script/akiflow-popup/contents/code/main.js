// On Wayland an application cannot position its own windows, so Electron's
// setBounds() is ignored and Akiflow's tray popup opens centred. KWin can place
// it: the cursor is still over the clicked panel widget when the popup maps.

function isTray(w) {
    return w && /^akiflow$/i.test(w.resourceClass || "") && w.caption === "Akiflow - Tray";
}

function place(w) {
    const c = workspace.cursorPos;
    // PlacementArea is the screen minus panels, so the popup never covers the panel.
    const a = workspace.clientArea(KWin.PlacementArea, workspace.screenAt(c), workspace.currentDesktop);
    const g = w.frameGeometry;
    const margin = 8;
    const overBottomPanel = c.y >= a.y + a.height;
    const overTopPanel = c.y < a.y;
    const overRightPanel = c.x >= a.x + a.width;
    const overLeftPanel = c.x < a.x;

    let x = Math.round(c.x - g.width / 2);
    let y = Math.round(c.y - g.height / 2);
    if (overBottomPanel) y = a.y + a.height - g.height - margin;
    else if (overTopPanel) y = a.y + margin;
    else if (overRightPanel) x = a.x + a.width - g.width - margin;
    else if (overLeftPanel) x = a.x + margin;

    x = Math.max(a.x + margin, Math.min(x, a.x + a.width - g.width - margin));
    y = Math.max(a.y + margin, Math.min(y, a.y + a.height - g.height - margin));
    w.frameGeometry = { x: x, y: y, width: g.width, height: g.height };
}

workspace.windowAdded.connect(function (w) {
    if (isTray(w)) place(w);
});
