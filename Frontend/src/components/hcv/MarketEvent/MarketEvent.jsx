import { useState, useRef, useEffect, useCallback } from "react";

// ── Constants ──────────────────────────────────────────────────────────────────
const PAYERS  = ["Commercial", "Medicare", "Medicaid"];
const BRANDS  = ["ASGA", "GILD", "OTHER"];
const METRICS = ["Market Share", "Market Volume"];
const CURVES  = ["Linear", "Logarithmic", "Exponential", "S-Curve"];
const EVENT_TYPES = ["Market", "Product", "Payer"];
const MONTHS  = ["Jan 26","Feb 26","Mar 26","Apr 26","May 26","Jun 26","Jul 26","Aug 26","Sep 26","Oct 26","Nov 26","Dec 26"];
const CHART_COLORS = ["#4F46E5","#10b981","#f59e0b","#ef4444","#8b5cf6","#06b6d4","#ec4899"];

const DEFAULT_EVENT = () => ({
  id: Date.now() + Math.random(),
  name: "New Event",
  eventType: "Market",
  segment: "All",
  target: "All",
  impacts: { Commercial: 100, Medicare: 0, Medicaid: 0 },
  start_date: "2026-01-01",
  start_val: 0,
  peak_val: 5,
  duration: 6,
  curve: "Linear",
  factor: 1,
});

// ── Shared design tokens ───────────────────────────────────────────────────────
const S = {
  toolbar: {
    background: "#fff", border: "1px solid #D8DEE8", borderRadius: 16,
    padding: "20px 24px", display: "flex", alignItems: "flex-end",
    gap: 24, flexWrap: "wrap",
  },
  group: { display: "flex", flexDirection: "column", gap: 6 },
  label: { fontSize: 11, fontWeight: 700, color: "#64748b", textTransform: "uppercase", letterSpacing: "0.04em" },
  trigger: (open) => ({
    height: 35, background: "#fcfcfd",
    border: `1px solid ${open ? "#4F46E5" : "#e2e8f0"}`,
    borderRadius: 8, padding: "0 10px 0 12px", minWidth: 160,
    display: "flex", alignItems: "center", justifyContent: "space-between",
    gap: 8, cursor: "pointer", userSelect: "none", boxSizing: "border-box",
  }),
  triggerText: { fontSize: 13, fontWeight: 500, color: "#1e293b", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: 150 },
  caret: (open) => ({ fontSize: 9, color: open ? "#4F46E5" : "#94a3b8", flexShrink: 0, transition: "transform 0.15s", transform: open ? "rotate(180deg)" : "none" }),
  menu: {
    position: "absolute", top: "calc(100% + 4px)", left: 0, zIndex: 999,
    background: "#fff", border: "1px solid #e2e8f0", borderRadius: 8,
    boxShadow: "0 4px 16px rgba(15,23,42,0.10), 0 1px 4px rgba(15,23,42,0.06)",
    padding: 6, minWidth: 180,
  },
  option: { display: "flex", alignItems: "center", gap: 9, padding: "7px 10px", fontSize: 13, fontWeight: 500, color: "#1e293b", borderRadius: 6, cursor: "pointer" },
  input: { width: 13, height: 13, cursor: "pointer", accentColor: "#4F46E5", flexShrink: 0 },
  btnRun: { height: 35, background: "#10b981", color: "#fff", border: "none", borderRadius: 8, padding: "0 18px", fontSize: 12, fontWeight: 700, cursor: "pointer", whiteSpace: "nowrap" },
};

// ── Utility hooks ──────────────────────────────────────────────────────────────
function useClickOutside(ref, fn) {
  useEffect(() => {
    const h = (e) => { if (ref.current && !ref.current.contains(e.target)) fn(); };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, [ref, fn]);
}

// ── Shared dropdown primitives ─────────────────────────────────────────────────
function MultiCheckDropdown({ triggerLabel, options, selected, onToggle }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useClickOutside(ref, () => setOpen(false));
  return (
    <div ref={ref} style={{ position: "relative" }}>
      <div onClick={() => setOpen((o) => !o)} style={S.trigger(open)}
        onMouseEnter={(e) => { if (!open) e.currentTarget.style.borderColor = "#94a3b8"; }}
        onMouseLeave={(e) => { if (!open) e.currentTarget.style.borderColor = "#e2e8f0"; }}>
        <span style={S.triggerText}>{triggerLabel}</span>
        <span style={S.caret(open)}>▼</span>
      </div>
      {open && (
        <div style={S.menu}>
          {options.map((opt) => (
            <label key={opt} style={S.option}
              onMouseEnter={(e) => (e.currentTarget.style.background = "#f1f5f9")}
              onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}>
              <input type="checkbox" checked={selected.includes(opt)} onChange={() => onToggle(opt)} style={S.input} />
              {opt}
            </label>
          ))}
        </div>
      )}
    </div>
  );
}

function RadioDropdown({ name, options, selected, onChange }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useClickOutside(ref, () => setOpen(false));
  return (
    <div ref={ref} style={{ position: "relative" }}>
      <div onClick={() => setOpen((o) => !o)} style={S.trigger(open)}
        onMouseEnter={(e) => { if (!open) e.currentTarget.style.borderColor = "#94a3b8"; }}
        onMouseLeave={(e) => { if (!open) e.currentTarget.style.borderColor = "#e2e8f0"; }}>
        <span style={S.triggerText}>{selected}</span>
        <span style={S.caret(open)}>▼</span>
      </div>
      {open && (
        <div style={S.menu}>
          {options.map((opt) => (
            <label key={opt} style={S.option}
              onMouseEnter={(e) => (e.currentTarget.style.background = "#f1f5f9")}
              onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}>
              <input type="radio" name={name} checked={selected === opt}
                onChange={() => { onChange(opt); setOpen(false); }} style={S.input} />
              {opt}
            </label>
          ))}
        </div>
      )}
    </div>
  );
}

function FilterGroup({ label, children }) {
  return (
    <div style={S.group}>
      <label style={S.label}>{label}</label>
      {children}
    </div>
  );
}

function makeLabel(selected, all, allLabel) {
  if (selected.length === 0) return "None";
  if (selected.length === all.length) return allLabel;
  return selected.join(", ");
}

// ── Inline cell input used in the event table ──────────────────────────────────
function CellInput({ value, onChange, type = "text", style = {} }) {
  return (
    <input
      type={type}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      style={{
        width: "100%", height: 28, border: "1px solid #e2e8f0", borderRadius: 6,
        padding: "0 7px", fontSize: 12, fontWeight: 500, color: "#1e293b",
        background: "#fcfcfd", outline: "none", boxSizing: "border-box", ...style,
      }}
      onFocus={(e) => (e.target.style.borderColor = "#4F46E5")}
      onBlur={(e) => (e.target.style.borderColor = "#e2e8f0")}
    />
  );
}

function CellSelect({ value, onChange, options }) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      style={{
        width: "100%", height: 28, border: "1px solid #e2e8f0", borderRadius: 6,
        padding: "0 6px", fontSize: 12, fontWeight: 500, color: "#1e293b",
        background: "#fcfcfd", outline: "none", cursor: "pointer", boxSizing: "border-box",
      }}
      onFocus={(e) => (e.target.style.borderColor = "#4F46E5")}
      onBlur={(e) => (e.target.style.borderColor = "#e2e8f0")}
    >
      {options.map((o) => (
        <option key={o.value ?? o} value={o.value ?? o}>{o.label ?? o}</option>
      ))}
    </select>
  );
}

// ── Impact popup modal ─────────────────────────────────────────────────────────
function ImpactModal({ event, onClose, onSave }) {
  const isPayer = event.eventType === "Payer";
  const keys = isPayer ? PAYERS : BRANDS;
  const [impacts, setImpacts] = useState({ ...event.impacts });

  const setVal = (k, v) => setImpacts((prev) => ({ ...prev, [k]: parseFloat(v) || 0 }));

  return (
    <div style={{
      position: "fixed", inset: 0, background: "rgba(15,23,42,0.45)",
      display: "flex", alignItems: "center", justifyContent: "center", zIndex: 3000,
    }}>
      <div style={{
        background: "#fff", borderRadius: 12, width: 320, padding: 24,
        boxShadow: "0 20px 40px rgba(15,23,42,0.18)",
      }}>
        <p style={{ margin: "0 0 16px", fontSize: 14, fontWeight: 700, color: "#0f172a" }}>
          {isPayer ? "Impacted Payers (%)" : "Impacted Brands (%)"}
        </p>
        {keys.map((k) => (
          <div key={k} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
            <span style={{ fontSize: 13, color: "#1e293b" }}>{k}</span>
            <input
              type="number" value={impacts[k] ?? 0}
              onChange={(e) => setVal(k, e.target.value)}
              style={{
                width: 70, height: 30, border: "1px solid #e2e8f0", borderRadius: 6,
                textAlign: "center", fontSize: 13, padding: "0 6px", outline: "none",
                background: "#fcfcfd", color: "#1e293b",
              }}
              onFocus={(e) => (e.target.style.borderColor = "#4F46E5")}
              onBlur={(e) => (e.target.style.borderColor = "#e2e8f0")}
            />
          </div>
        ))}
        <div style={{ display: "flex", gap: 8, marginTop: 20 }}>
          <button onClick={onClose} style={{
            flex: 1, height: 34, background: "#f1f5f9", border: "1px solid #e2e8f0",
            borderRadius: 8, fontSize: 13, fontWeight: 600, cursor: "pointer", color: "#64748b",
          }}>Cancel</button>
          <button onClick={() => { onSave(impacts); onClose(); }} style={{
            flex: 1, height: 34, background: "#4F46E5", border: "none",
            borderRadius: 8, fontSize: 13, fontWeight: 600, cursor: "pointer", color: "#fff",
          }}>Done</button>
        </div>
      </div>
    </div>
  );
}

// ── Delete confirm modal ───────────────────────────────────────────────────────
function DeleteModal({ onCancel, onConfirm }) {
  return (
    <div style={{
      position: "fixed", inset: 0, background: "rgba(15,23,42,0.45)",
      display: "flex", alignItems: "center", justifyContent: "center", zIndex: 3000,
    }}>
      <div style={{ background: "#fff", borderRadius: 12, width: 320, padding: 24, boxShadow: "0 20px 40px rgba(15,23,42,0.18)" }}>
        <p style={{ margin: "0 0 6px", fontSize: 14, fontWeight: 700, color: "#ef4444" }}>Delete event?</p>
        <p style={{ margin: "0 0 20px", fontSize: 13, color: "#64748b", lineHeight: 1.5 }}>
          This action cannot be undone.
        </p>
        <div style={{ display: "flex", gap: 8 }}>
          <button onClick={onCancel} style={{
            flex: 1, height: 34, background: "#f1f5f9", border: "1px solid #e2e8f0",
            borderRadius: 8, fontSize: 13, fontWeight: 600, cursor: "pointer", color: "#64748b",
          }}>Cancel</button>
          <button onClick={onConfirm} style={{
            flex: 1, height: 34, background: "#ef4444", border: "none",
            borderRadius: 8, fontSize: 13, fontWeight: 600, cursor: "pointer", color: "#fff",
          }}>Delete</button>
        </div>
      </div>
    </div>
  );
}

// ── Row action menu (⋮) ────────────────────────────────────────────────────────
function RowMenu({ onDuplicate, onDelete }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useClickOutside(ref, () => setOpen(false));
  return (
    <div ref={ref} style={{ position: "relative", display: "flex", justifyContent: "center" }}>
      <button onClick={(e) => { e.stopPropagation(); setOpen((o) => !o); }}
        style={{ background: "none", border: "none", cursor: "pointer", fontSize: 18, color: "#94a3b8", lineHeight: 1, padding: "2px 4px" }}>
        ⋮
      </button>
      {open && (
        <div style={{
          position: "absolute", right: 0, top: 28, background: "#fff",
          border: "1px solid #e2e8f0", borderRadius: 8,
          boxShadow: "0 4px 16px rgba(15,23,42,0.12)", zIndex: 200, minWidth: 120, overflow: "hidden",
        }}>
          <div onClick={() => { onDuplicate(); setOpen(false); }}
            style={{ padding: "9px 14px", fontSize: 12, fontWeight: 500, cursor: "pointer", color: "#1e293b" }}
            onMouseEnter={(e) => (e.currentTarget.style.background = "#f1f5f9")}
            onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}>
            Duplicate
          </div>
          <div onClick={() => { onDelete(); setOpen(false); }}
            style={{ padding: "9px 14px", fontSize: 12, fontWeight: 500, cursor: "pointer", color: "#ef4444" }}
            onMouseEnter={(e) => (e.currentTarget.style.background = "#fef2f2")}
            onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}>
            Delete
          </div>
        </div>
      )}
    </div>
  );
}

// ── Add event dropdown ─────────────────────────────────────────────────────────
function AddEventDropdown({ onAdd }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useClickOutside(ref, () => setOpen(false));
  return (
    <div ref={ref} style={{ position: "relative" }} onClick={(e) => e.stopPropagation()}>
      <button onClick={() => setOpen((o) => !o)} style={{
        height: 30, background: "#4F46E5", color: "#fff", border: "none", borderRadius: 6,
        padding: "0 12px", fontSize: 11, fontWeight: 700, cursor: "pointer", display: "flex",
        alignItems: "center", gap: 5,
      }}>
        + Add New Event <span style={{ fontSize: 9 }}>▼</span>
      </button>
      {open && (
        <div style={{
          position: "absolute", right: 0, top: "calc(100% + 4px)", background: "#fff",
          border: "1px solid #e2e8f0", borderRadius: 8,
          boxShadow: "0 4px 16px rgba(15,23,42,0.12)", zIndex: 2500, minWidth: 150, overflow: "hidden",
        }}>
          {EVENT_TYPES.map((t) => (
            <div key={t} onClick={() => { onAdd(t); setOpen(false); }}
              style={{ padding: "9px 14px", fontSize: 12, fontWeight: 600, cursor: "pointer", color: "#1e293b" }}
              onMouseEnter={(e) => (e.currentTarget.style.background = "#f1f5f9")}
              onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}>
              {t} Event
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Curve math ────────────────────────────────────────────────────────────────
function computeCurveValues(ev) {
  const startIdx = new Date(ev.start_date).getMonth();
  const k = ev.factor || 1;
  return MONTHS.map((_, i) => {
    if (i < startIdx) return ev.start_val;
    const t = i - startIdx;
    const progress = Math.min(t / Math.max(ev.duration, 1), 1);
    let f = 0;
    if (ev.curve === "S-Curve")        f = 1 / (1 + Math.exp(-k * (progress - 0.5)));
    else if (ev.curve === "Exponential") f = (Math.exp(k * progress) - 1) / (Math.exp(k) - 1 || 1);
    else if (ev.curve === "Logarithmic") f = Math.log(1 + k * progress) / (Math.log(1 + k) || 1);
    else                                 f = progress * k; // Linear
    f = Math.min(Math.max(f, 0), 1);
    return parseFloat((ev.start_val + f * (ev.peak_val - ev.start_val)).toFixed(4));
  });
}

// ── Plotly curve preview chart ─────────────────────────────────────────────────
function CurvePreviewChart({ events }) {
  const divRef = useRef(null);

  useEffect(() => {
    if (!divRef.current || typeof window.Plotly === "undefined") return;

    if (!events.length) {
      window.Plotly.react(divRef.current, [], {
        paper_bgcolor: "#fff", plot_bgcolor: "#fff",
        margin: { l: 44, r: 12, t: 8, b: 80 }, height: 270, autosize: true,
        annotations: [{
          text: "No events to preview", showarrow: false,
          font: { size: 13, color: "#94a3b8", family: "Inter, sans-serif" },
          xref: "paper", yref: "paper", x: 0.5, y: 0.5,
        }],
        xaxis: { visible: false }, yaxis: { visible: false },
      }, { displayModeBar: false, responsive: true });
      return;
    }

    const traces = [];

    events.forEach((ev, idx) => {
      const color = CHART_COLORS[idx % CHART_COLORS.length];
      const vals  = computeCurveValues(ev);
      const si    = new Date(ev.start_date).getMonth();
      const di    = Math.min(si + ev.duration, 11);

      // ── Pre-start flat segment (before event fires) — thin solid ──
      if (si > 0) {
        traces.push({
          x: MONTHS.slice(0, si + 1),
          y: vals.slice(0, si + 1),
          type: "scatter", mode: "lines",
          name: ev.name, legendgroup: ev.name, showlegend: false,
          line: { color, width: 1.5, dash: "solid" },
          hovertemplate: "%{y:.2f}%<extra></extra>",
        });
      }

      // ── Ramp segment: start → peak (solid + markers) ──
      traces.push({
        x: MONTHS.slice(si, di + 1),
        y: vals.slice(si, di + 1),
        type: "scatter", mode: "lines+markers",
        name: ev.name, legendgroup: ev.name, showlegend: true,
        line: { color, width: 2.5, dash: "solid", shape: "spline", smoothing: 0.8 },
        marker: { color, size: 5, symbol: "circle" },
        hovertemplate: "%{y:.2f}%<extra>" + ev.name + "</extra>",
      });

      // ── Post-peak flat segment — dotted ──
      if (di < 11) {
        traces.push({
          x: MONTHS.slice(di, 12),
          y: vals.slice(di, 12),
          type: "scatter", mode: "lines",
          name: ev.name, legendgroup: ev.name, showlegend: false,
          line: { color, width: 2, dash: "dot" },
          hovertemplate: "%{y:.2f}%<extra></extra>",
        });
      }
    });

    const layout = {
      paper_bgcolor: "#ffffff",
      plot_bgcolor:  "#ffffff",
      margin: { l: 44, r: 12, t: 8, b: 100 },
      height: 270,
      autosize: true,
      xaxis: {
        tickfont: { family: "Inter, sans-serif", size: 10, color: "#64748b" },
        tickangle: -45,
        showgrid: true,
        gridcolor: "#f1f5f9",
        gridwidth: 1,
        zeroline: false,
        linecolor: "#e2e8f0",
        linewidth: 1,
        fixedrange: true,
      },
      yaxis: {
        title: { text: "Impact (%)", font: { family: "Inter, sans-serif", size: 10, color: "#64748b" }, standoff: 4 },
        tickfont: { family: "Inter, sans-serif", size: 10, color: "#64748b" },
        showgrid: false,
        zeroline: true,
        zerolinecolor: "#e2e8f0",
        zerolinewidth: 1,
        fixedrange: true,
      },
      legend: {
        orientation: "h",
        x: 0.5, xanchor: "center",
        y: -0.40, yanchor: "top",
        font: { family: "Inter, sans-serif", size: 10, color: "#1e293b" },
        bgcolor: "rgba(0,0,0,0)",
        itemwidth: 10,
        traceorder: "normal",
      },
      hovermode: "x unified",
      hoverlabel: {
        bgcolor: "#1e293b", bordercolor: "#1e293b",
        font: { family: "Inter, sans-serif", size: 11, color: "#fff" },
        namelength: -1,
      },
    };

    window.Plotly.react(divRef.current, traces, layout, { displayModeBar: false, responsive: true });
  }, [events]);

  return <div ref={divRef} style={{ width: "100%", minHeight: 270 }} />;
}

// ── Constants for tab section ─────────────────────────────────────────────────
const EVENT_TABS = [
  { label: "Payer Event",  value: "payer_event"  },
  { label: "Product Event", value: "product_event" },
  { label: "Overall Event", value: "overall_event" },
];

const CURVE_TYPES    = ["Linear", "Logarithmic", "Exponential", "S-Curve"];
const PAYER_OPTIONS  = ["Commercial", "Medicare", "Medicaid"];
const PRODUCT_OPTIONS = ["GILD", "ASGA", "others"];

const AVAILABLE_MONTHS_OPTS = [
  "2026-01-01","2026-02-01","2026-03-01","2026-04-01",
  "2026-05-01","2026-06-01","2026-07-01","2026-08-01",
  "2026-09-01","2026-10-01","2026-11-01","2026-12-01",
];
function fmtMonth(v) {
  if (!v) return "";
  const d = new Date(v);
  return d.toLocaleDateString("en-US", { month: "short", year: "2-digit" });
}

// ── Shared table input styles ─────────────────────────────────────────────────
const tblInp = {
  height: 32, width: "100%", border: "1px solid #e2e8f0", borderRadius: 6,
  padding: "0 8px", fontSize: 13, color: "#1e293b", background: "#fff",
  outline: "none", boxSizing: "border-box",
};
const tblSel = {
  height: 32, width: "100%", border: "1px solid #e2e8f0", borderRadius: 6,
  padding: "0 8px", fontSize: 13, color: "#1e293b", background: "#fff",
  outline: "none", cursor: "pointer", appearance: "none", WebkitAppearance: "none",
  boxSizing: "border-box",
};

function TblSelect({ value, onChange, options, placeholder = "Select", disabled = false }) {
  return (
    <div style={{ position: "relative" }}>
      <select
        value={value} onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        style={{ ...tblSel, color: value ? "#1e293b" : "#94a3b8", paddingRight: 24 }}
        onFocus={(e) => (e.target.style.borderColor = "#4F46E5")}
        onBlur={(e)  => (e.target.style.borderColor = "#e2e8f0")}
      >
        <option value="" disabled>{placeholder}</option>
        {options.map((o) => {
          const v = o.value ?? o; const l = o.label ?? o;
          return <option key={v} value={v}>{l}</option>;
        })}
      </select>
      <span style={{ position:"absolute", right:8, top:"50%", transform:"translateY(-50%)", fontSize:9, color:"#94a3b8", pointerEvents:"none" }}>▼</span>
    </div>
  );
}

// Multi-select for Products / Markets inside rows
function TblMultiSelect({ value, onChange, options, placeholder = "Select" }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useClickOutside(ref, () => setOpen(false));
  const label = value.length === 0 ? placeholder : value.join(", ");
  const toggle = (opt) => onChange(value.includes(opt) ? value.filter((v) => v !== opt) : [...value, opt]);
  return (
    <div ref={ref} style={{ position: "relative" }}>
      <div
        onClick={() => setOpen((o) => !o)}
        style={{
          ...tblSel, display:"flex", alignItems:"center", justifyContent:"space-between",
          cursor:"pointer", userSelect:"none", paddingRight:24,
          color: value.length ? "#1e293b" : "#94a3b8",
          borderColor: open ? "#4F46E5" : "#e2e8f0",
          overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap",
        }}
      >
        <span style={{ overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap", fontSize:13 }}>{label}</span>
        <span style={{ fontSize:9, color:"#94a3b8", position:"absolute", right:8 }}>▼</span>
      </div>
      {open && (
        <div style={{
          position:"absolute", top:"calc(100% + 3px)", left:0, zIndex:999,
          background:"#fff", border:"1px solid #e2e8f0", borderRadius:8,
          boxShadow:"0 4px 16px rgba(15,23,42,.12)", padding:6, minWidth:160,
        }}>
          {options.map((opt) => (
            <label key={opt} style={{ display:"flex", alignItems:"center", gap:8, padding:"6px 8px", fontSize:12, fontWeight:500, color:"#1e293b", borderRadius:4, cursor:"pointer" }}
              onMouseEnter={(e) => (e.currentTarget.style.background = "#f1f5f9")}
              onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}>
              <input type="checkbox" checked={value.includes(opt)} onChange={() => toggle(opt)}
                style={{ width:13, height:13, accentColor:"#4F46E5", flexShrink:0, cursor:"pointer" }} />
              {opt}
            </label>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Row action menu ───────────────────────────────────────────────────────────
function RowActionMenu({ onDuplicate, onDelete }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useClickOutside(ref, () => setOpen(false));
  return (
    <div ref={ref} style={{ position:"relative", display:"flex", justifyContent:"center" }}>
      <button onClick={(e) => { e.stopPropagation(); setOpen((o) => !o); }}
        style={{ background:"none", border:"none", cursor:"pointer", color:"#64748b", padding:"2px 6px", fontSize:18, lineHeight:1 }}>
        ⋮
      </button>
      {open && (
        <div style={{
          position:"absolute", right:0, top:28, background:"#fff",
          border:"1px solid #e2e8f0", borderRadius:8,
          boxShadow:"0 4px 16px rgba(15,23,42,.12)", zIndex:300, minWidth:120, overflow:"hidden",
        }}>
          <div onClick={() => { onDuplicate(); setOpen(false); }}
            style={{ padding:"9px 14px", fontSize:13, cursor:"pointer", color:"#1e293b" }}
            onMouseEnter={(e) => (e.currentTarget.style.background = "#f1f5f9")}
            onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}>
            Duplicate
          </div>
          <div onClick={() => { onDelete(); setOpen(false); }}
            style={{ padding:"9px 14px", fontSize:13, cursor:"pointer", color:"#ef4444" }}
            onMouseEnter={(e) => (e.currentTarget.style.background = "#fef2f2")}
            onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}>
            Delete
          </div>
        </div>
      )}
    </div>
  );
}

// ── Impact Source Dialog ──────────────────────────────────────────────────────
function ImpactDialog({ open, onClose, isMarketEvent, value, onChange }) {
  if (!open) return null;
  const opts = isMarketEvent ? PAYER_OPTIONS : PRODUCT_OPTIONS;
  const title = isMarketEvent ? "Edit Impacted Payers" : "Edit Impacted Products";
  return (
    <div style={{ position:"fixed", inset:0, background:"rgba(15,23,42,0.45)", display:"flex", alignItems:"center", justifyContent:"center", zIndex:3000 }}>
      <div style={{ background:"#fff", borderRadius:12, width:420, padding:24, boxShadow:"0 20px 40px rgba(15,23,42,.18)" }}>
        <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:16 }}>
          <span style={{ fontSize:15, fontWeight:700, color:"#0f172a" }}>{title}</span>
          <button onClick={onClose} style={{ background:"none", border:"none", cursor:"pointer", fontSize:18, color:"#64748b" }}>✕</button>
        </div>
        <p style={{ fontSize:13, color:"#64748b", marginBottom:16, fontWeight:600 }}>Select impacted items</p>
        <div style={{ border:"1px solid #e2e8f0", borderRadius:8, overflow:"hidden" }}>
          {opts.map((opt) => (
            <label key={opt} style={{ display:"flex", alignItems:"center", gap:10, padding:"10px 14px", fontSize:13, color:"#1e293b", cursor:"pointer", borderBottom:"1px solid #f1f5f9" }}
              onMouseEnter={(e) => (e.currentTarget.style.background = "#f8fafc")}
              onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}>
              <input type="checkbox" checked={value.includes(opt)} onChange={() => {
                onChange(value.includes(opt) ? value.filter((v) => v !== opt) : [...value, opt]);
              }} style={{ width:14, height:14, accentColor:"#4F46E5", cursor:"pointer" }} />
              {opt}
            </label>
          ))}
        </div>
        <div style={{ display:"flex", gap:8, marginTop:20, justifyContent:"flex-end" }}>
          <button onClick={onClose} style={{ height:34, padding:"0 16px", background:"#f1f5f9", border:"1px solid #e2e8f0", borderRadius:8, fontSize:13, fontWeight:600, cursor:"pointer", color:"#64748b" }}>Cancel</button>
          <button onClick={onClose} style={{ height:34, padding:"0 16px", background:"#4F46E5", border:"none", borderRadius:8, fontSize:13, fontWeight:600, cursor:"pointer", color:"#fff" }}>Apply</button>
        </div>
      </div>
    </div>
  );
}

// ── Delete Dialog ─────────────────────────────────────────────────────────────
function DeleteDialog({ open, onClose, onConfirm }) {
  if (!open) return null;
  return (
    <div style={{ position:"fixed", inset:0, background:"rgba(15,23,42,0.45)", display:"flex", alignItems:"center", justifyContent:"center", zIndex:3000 }}>
      <div style={{ background:"#fff", borderRadius:12, width:360, padding:24, boxShadow:"0 20px 40px rgba(15,23,42,.18)" }}>
        <p style={{ fontSize:15, fontWeight:700, color:"#0f172a", marginBottom:8 }}>Delete Event</p>
        <p style={{ fontSize:13, color:"#64748b", marginBottom:24 }}>Are you sure you want to delete this event?</p>
        <div style={{ display:"flex", gap:8, justifyContent:"flex-end" }}>
          <button onClick={onClose} style={{ height:34, padding:"0 16px", background:"#f1f5f9", border:"1px solid #e2e8f0", borderRadius:8, fontSize:13, fontWeight:600, cursor:"pointer", color:"#64748b" }}>Cancel</button>
          <button onClick={onConfirm} style={{ height:34, padding:"0 16px", background:"#ef4444", border:"none", borderRadius:8, fontSize:13, fontWeight:600, cursor:"pointer", color:"#fff" }}>Delete</button>
        </div>
      </div>
    </div>
  );
}

// ── createEmptyRow ────────────────────────────────────────────────────────────
function createEmptyRow() {
  return {
    id: Date.now() + Math.random(),
    event_name: "",
    products: [],
    markets: [],
    impacted_items: [],
    start_date: "",
    peak_percent: "",
    months: "",
    curve_type: CURVE_TYPES[0],
    factor: "",
    enable_coverage: false,
    coverage_peak_percent: "",
    coverage_peak_months: "",
  };
}

// ── ImpactCurveSection — tab-based (Market / Product / Overall) ───────────────
function ImpactCurveSection() {
  const [activeTab,          setActiveTab]          = useState("market_event");
  const [rows,               setRows]               = useState([createEmptyRow()]);
  const [collapsed,          setCollapsed]          = useState(false);
  const [deleteIdx,          setDeleteIdx]          = useState(null);
  const [impactIdx,          setImpactIdx]          = useState(null);
  const [openDelete,         setOpenDelete]         = useState(false);
  const [openImpact,         setOpenImpact]         = useState(false);

  const isMarketEvent  = activeTab === "market_event";
  const isProductEvent = activeTab === "product_event";
  const isOverallEvent = activeTab === "overall_event";

  // Reset rows when tab changes
  useEffect(() => { setRows([createEmptyRow()]); }, [activeTab]);

  const handleRowChange = (idx, field, value) => {
    setRows((prev) => prev.map((r, i) => i === idx ? { ...r, [field]: value } : r));
  };

  const handleAdd = () => setRows((prev) => [...prev, createEmptyRow()]);

  const handleDuplicate = (idx) => {
    setRows((prev) => {
      const copy = { ...prev[idx], id: Date.now() + Math.random(),
        products: [...prev[idx].products], markets: [...prev[idx].markets], impacted_items: [...prev[idx].impacted_items] };
      const next = [...prev];
      next.splice(idx + 1, 0, copy);
      return next;
    });
  };

  const handleDelete = () => {
    setRows((prev) => prev.filter((_, i) => i !== deleteIdx));
    setOpenDelete(false);
    setDeleteIdx(null);
  };

  // Column grid — exact values from HIVMarketEvent headerColumns
  const gridCols = isOverallEvent
    ? "0.7fr 0.4fr 0.28fr 0.28fr 0.38fr 0.25fr 0.35fr 0.35fr 40px"
    : "0.7fr 0.55fr 0.45fr 0.55fr 0.4fr 0.28fr 0.28fr 0.38fr 0.25fr 0.28fr 0.35fr 0.35fr 40px";

  const headers = isOverallEvent
    ? ["Overall Event","Start Date","Peak %","Months","Curve","Factor","Coverage","Coverage Peak %","Coverage Peak Months",""]
    : [
        isMarketEvent ? "Payer Event" : "Product Event",
        "Products","Markets",
        isMarketEvent ? "Impacted Markets" : "Impacted Products",
        "Start Date","Peak %","Months","Curve","Factor","Coverage",
        "Coverage Peak %","Coverage Peak Months","",
      ];

  // ── Shared cell padding — matches source gap:2 + px:2 spacing ──
  const cellStyle = { display:"flex", alignItems:"center" };

  return (
    <>
      {/* ── Tabs — Box sx={{ mt:3 }} inside Paper, outside Accordion ── */}
      <div style={{ marginTop: 24, borderBottom: "1px solid #e2e8f0" }}>
        <div style={{ display: "flex" }}>
          {EVENT_TABS.map((tab) => {
            const active = tab.value === activeTab;
            return (
              <button
                key={tab.value}
                onClick={() => setActiveTab(tab.value)}
                style={{
                  padding: "12px 16px",
                  fontSize: 14,
                  fontWeight: active ? 700 : 500,
                  color: active ? "#4F46E5" : "#64748b",
                  background: "none",
                  border: "none",
                  borderBottom: active ? "2px solid #4F46E5" : "2px solid transparent",
                  marginBottom: -1,
                  cursor: "pointer",
                  textTransform: "none",
                  letterSpacing: 0,
                  transition: "color 0.15s",
                }}
              >
                {tab.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* ── Accordion — mt:2, border #D8DEE8, borderRadius 12px, no shadow ── */}
      <div style={{
        marginTop: 16,
        borderRadius: 12,
        border: "1px solid #D8DEE8",
        overflow: "hidden",
        boxShadow: "none",
        background: "#fff",
      }}>

        {/* AccordionSummary — expand icon on left via ExpandMoreIcon, title + buttons ── */}
        <div
          style={{
            display: "flex", alignItems: "center", gap: 8,
            padding: "14px 16px",
            cursor: "pointer",
            background: "#fff",
            borderBottom: collapsed ? "none" : "1px solid #e2e8f0",
            userSelect: "none",
          }}
          onClick={() => setCollapsed((c) => !c)}
        >
          {/* ExpandMoreIcon equivalent — rotates when collapsed */}
          <span style={{
            display: "inline-flex", alignItems: "center", justifyContent: "center",
            width: 24, height: 24, color: "#64748b",
            transition: "transform 0.2s",
            transform: collapsed ? "rotate(-90deg)" : "rotate(0deg)",
            fontSize: 20, flexShrink: 0,
          }}>
            ▾
          </span>

          {/* Title + action buttons — justifyContent: space-between, width: 100% ── */}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", width: "100%" }}>
            <span style={{ fontSize: 14, fontWeight: 700, color: "#1e293b" }}>
              Impact Curve Configuration
            </span>
            <div style={{ display: "flex", gap: 12 }} onClick={(e) => e.stopPropagation()}>
              <button style={{
                height: 33, padding: "0 12px", background: "#4F46E5", color: "#fff",
                border: "none", borderRadius: 8, fontSize: 13, fontWeight: 600,
                cursor: "pointer", textTransform: "none",
              }}>
                Run Calculation
              </button>
              <button onClick={handleAdd} style={{
                height: 33, padding: "0 12px", background: "#4F46E5", color: "#fff",
                border: "none", borderRadius: 8, fontSize: 13, fontWeight: 600,
                cursor: "pointer", whiteSpace: "nowrap", textTransform: "none",
              }}>
                + Add New Event
              </button>
            </div>
          </div>
        </div>

        {/* AccordionDetails → nested Paper for the table ── */}
        {!collapsed && (
          <div style={{ padding: "16px 16px 16px" }}>
            <div style={{
              marginTop: 8,
              border: "1px solid #D8DEE8",
              borderRadius: 12,
              overflowX: "auto",
              overflowY: "auto",
              maxHeight: 380,
              boxShadow: "none",
            }}>
              <div style={{ minWidth: isOverallEvent ? 900 : 1450 }}>

                {/* ── Header — bg #f8fafc, gap:2(16px), px:2(16px), py:1.5(12px), border-bottom #D8DEE8 ── */}
                <div style={{
                  display: "grid",
                  gridTemplateColumns: gridCols,
                  gap: 16,
                  padding: "12px 16px",
                  backgroundColor: "#f8fafc",
                  borderBottom: "1px solid #D8DEE8",
                }}>
                  {headers.map((h, i) => (
                    <div key={i} style={{ fontSize: 13, fontWeight: 700, color: "#64748b" }}>
                      {h}
                    </div>
                  ))}
                </div>

                {/* ── Data rows — gap:2(16px), px:2(16px), py:1.5(12px), no alternating bg ── */}
                {rows.map((row, idx) => (
                  <div
                    key={row.id}
                    style={{
                      display: "grid",
                      gridTemplateColumns: gridCols,
                      gap: 16,
                      padding: "12px 16px",
                      alignItems: "center",
                      borderBottom: idx < rows.length - 1 ? "1px solid #f1f5f9" : "none",
                      background: "#fff",
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = "#f8fafc")}
                    onMouseLeave={(e) => (e.currentTarget.style.background = "#fff")}
                  >
                    {/* ── MARKET / PRODUCT EVENT columns ── */}
                    {(isMarketEvent || isProductEvent) && (<>
                      <div style={cellStyle}>
                        <input value={row.event_name}
                          placeholder={isMarketEvent ? "Payer Event" : "Product Event"}
                          onChange={(e) => handleRowChange(idx, "event_name", e.target.value)}
                          style={tblInp}
                          onFocus={(e) => (e.target.style.borderColor = "#4F46E5")}
                          onBlur={(e)  => (e.target.style.borderColor = "#e2e8f0")} />
                      </div>
                      <div style={cellStyle}>
                        <TblMultiSelect value={row.products} onChange={(v) => handleRowChange(idx, "products", v)}
                          options={PRODUCT_OPTIONS} placeholder="Select" />
                      </div>
                      <div style={cellStyle}>
                        <TblMultiSelect value={row.markets} onChange={(v) => handleRowChange(idx, "markets", v)}
                          options={PAYER_OPTIONS} placeholder="Select" />
                      </div>
                      <div style={cellStyle}>
                        <button
                          onClick={() => { setImpactIdx(idx); setOpenImpact(true); }}
                          style={{
                            height: 32, padding: "0 12px", background: "#fff",
                            border: "1px solid #4F46E5", borderRadius: 6,
                            fontSize: 12, fontWeight: 600, color: "#4F46E5",
                            cursor: "pointer", whiteSpace: "nowrap", textTransform: "none",
                          }}
                          onMouseEnter={(e) => (e.currentTarget.style.background = "#eef2ff")}
                          onMouseLeave={(e) => (e.currentTarget.style.background = "#fff")}>
                          Edit Source
                        </button>
                      </div>
                      <div style={cellStyle}>
                        <TblSelect value={row.start_date} onChange={(v) => handleRowChange(idx, "start_date", v)}
                          options={AVAILABLE_MONTHS_OPTS.map((m) => ({ value: m, label: fmtMonth(m) }))} />
                      </div>
                      <div style={cellStyle}>
                        <input value={row.peak_percent} onChange={(e) => handleRowChange(idx, "peak_percent", e.target.value)}
                          style={tblInp} onFocus={(e) => (e.target.style.borderColor = "#4F46E5")} onBlur={(e) => (e.target.style.borderColor = "#e2e8f0")} />
                      </div>
                      <div style={cellStyle}>
                        <input value={row.months} onChange={(e) => handleRowChange(idx, "months", e.target.value)}
                          style={tblInp} onFocus={(e) => (e.target.style.borderColor = "#4F46E5")} onBlur={(e) => (e.target.style.borderColor = "#e2e8f0")} />
                      </div>
                      <div style={cellStyle}>
                        <TblSelect value={row.curve_type} onChange={(v) => handleRowChange(idx, "curve_type", v)} options={CURVE_TYPES} />
                      </div>
                      <div style={cellStyle}>
                        <input value={row.factor} disabled={row.curve_type === "Linear"}
                          onChange={(e) => handleRowChange(idx, "factor", e.target.value)}
                          style={{ ...tblInp, opacity: row.curve_type === "Linear" ? 0.45 : 1 }}
                          onFocus={(e) => (e.target.style.borderColor = "#4F46E5")} onBlur={(e) => (e.target.style.borderColor = "#e2e8f0")} />
                      </div>
                      {/* Coverage toggle — Switch for Product, dash for Market ── */}
                      <div style={{ ...cellStyle, justifyContent: "center" }}>
                        {isProductEvent ? (
                          <div
                            onClick={() => handleRowChange(idx, "enable_coverage", !row.enable_coverage)}
                            style={{
                              width: 36, height: 20, borderRadius: 10, cursor: "pointer",
                              background: row.enable_coverage ? "#4F46E5" : "#e2e8f0",
                              position: "relative", flexShrink: 0, transition: "background .2s",
                            }}>
                            <div style={{
                              position: "absolute", top: 2, left: row.enable_coverage ? 18 : 2,
                              width: 16, height: 16, borderRadius: "50%", background: "#fff",
                              transition: "left .2s", boxShadow: "0 1px 3px rgba(0,0,0,.2)",
                            }} />
                          </div>
                        ) : (
                          <span style={{ fontSize: 11, color: "#94a3b8" }}>—</span>
                        )}
                      </div>
                      <div style={cellStyle}>
                        <input value={row.coverage_peak_percent}
                          disabled={isProductEvent ? !row.enable_coverage : false}
                          onChange={(e) => handleRowChange(idx, "coverage_peak_percent", e.target.value)}
                          style={{ ...tblInp, opacity: (isProductEvent && !row.enable_coverage) ? 0.45 : 1 }}
                          onFocus={(e) => (e.target.style.borderColor = "#4F46E5")} onBlur={(e) => (e.target.style.borderColor = "#e2e8f0")} />
                      </div>
                      <div style={cellStyle}>
                        <input value={row.coverage_peak_months}
                          disabled={isProductEvent ? !row.enable_coverage : false}
                          onChange={(e) => handleRowChange(idx, "coverage_peak_months", e.target.value)}
                          style={{ ...tblInp, opacity: (isProductEvent && !row.enable_coverage) ? 0.45 : 1 }}
                          onFocus={(e) => (e.target.style.borderColor = "#4F46E5")} onBlur={(e) => (e.target.style.borderColor = "#e2e8f0")} />
                      </div>
                    </>)}

                    {/* ── OVERALL EVENT columns ── */}
                    {isOverallEvent && (<>
                      <div style={cellStyle}>
                        <input value={row.event_name} placeholder="Overall Event"
                          onChange={(e) => handleRowChange(idx, "event_name", e.target.value)}
                          style={tblInp}
                          onFocus={(e) => (e.target.style.borderColor = "#4F46E5")} onBlur={(e) => (e.target.style.borderColor = "#e2e8f0")} />
                      </div>
                      <div style={cellStyle}>
                        <TblSelect value={row.start_date} onChange={(v) => handleRowChange(idx, "start_date", v)}
                          options={AVAILABLE_MONTHS_OPTS.map((m) => ({ value: m, label: fmtMonth(m) }))} />
                      </div>
                      <div style={cellStyle}>
                        <input value={row.peak_percent} onChange={(e) => handleRowChange(idx, "peak_percent", e.target.value)}
                          style={tblInp} onFocus={(e) => (e.target.style.borderColor = "#4F46E5")} onBlur={(e) => (e.target.style.borderColor = "#e2e8f0")} />
                      </div>
                      <div style={cellStyle}>
                        <input value={row.months} onChange={(e) => handleRowChange(idx, "months", e.target.value)}
                          style={tblInp} onFocus={(e) => (e.target.style.borderColor = "#4F46E5")} onBlur={(e) => (e.target.style.borderColor = "#e2e8f0")} />
                      </div>
                      <div style={cellStyle}>
                        <TblSelect value={row.curve_type} onChange={(v) => handleRowChange(idx, "curve_type", v)} options={CURVE_TYPES} />
                      </div>
                      <div style={cellStyle}>
                        <input value={row.factor} disabled={row.curve_type === "Linear"}
                          onChange={(e) => handleRowChange(idx, "factor", e.target.value)}
                          style={{ ...tblInp, opacity: row.curve_type === "Linear" ? 0.45 : 1 }}
                          onFocus={(e) => (e.target.style.borderColor = "#4F46E5")} onBlur={(e) => (e.target.style.borderColor = "#e2e8f0")} />
                      </div>
                      <div style={cellStyle}>
                        <input value={row.coverage_peak_percent} onChange={(e) => handleRowChange(idx, "coverage_peak_percent", e.target.value)}
                          style={tblInp} onFocus={(e) => (e.target.style.borderColor = "#4F46E5")} onBlur={(e) => (e.target.style.borderColor = "#e2e8f0")} />
                      </div>
                      <div style={cellStyle}>
                        <input value={row.coverage_peak_months} onChange={(e) => handleRowChange(idx, "coverage_peak_months", e.target.value)}
                          style={tblInp} onFocus={(e) => (e.target.style.borderColor = "#4F46E5")} onBlur={(e) => (e.target.style.borderColor = "#e2e8f0")} />
                      </div>
                    </>)}

                    {/* ── Row ⋮ menu ── */}
                    <div style={{ display: "flex", justifyContent: "center", alignItems: "center" }}>
                      <RowActionMenu
                        onDuplicate={() => handleDuplicate(idx)}
                        onDelete={() => { setDeleteIdx(idx); setOpenDelete(true); }}
                      />
                    </div>
                  </div>
                ))}

              </div>
            </div>
          </div>
        )}
      </div>

      {/* ── Dialogs ── */}
      <ImpactDialog
        open={openImpact}
        onClose={() => setOpenImpact(false)}
        isMarketEvent={isMarketEvent}
        value={impactIdx !== null ? rows[impactIdx]?.impacted_items || [] : []}
        onChange={(v) => { if (impactIdx !== null) handleRowChange(impactIdx, "impacted_items", v); }}
      />
      <DeleteDialog
        open={openDelete}
        onClose={() => setOpenDelete(false)}
        onConfirm={handleDelete}
      />
    </>
  );
}
// ── SingleSelectDropdown ──────────────────────────────────────────────────────
// Used for Scenario Name, From Date, To Date
function SingleSelectDropdown({ value, onChange, options, placeholder = "Select" }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useClickOutside(ref, () => setOpen(false));

  const displayLabel = value
    ? (options.find((o) => (o.value ?? o) === value)?.label ?? value)
    : placeholder;

  return (
    <div ref={ref} style={{ position: "relative" }}>
      <div
        onClick={() => setOpen((o) => !o)}
        style={S.trigger(open)}
        onMouseEnter={(e) => { if (!open) e.currentTarget.style.borderColor = "#94a3b8"; }}
        onMouseLeave={(e) => { if (!open) e.currentTarget.style.borderColor = open ? "#4F46E5" : "#e2e8f0"; }}
      >
        <span style={{ ...S.triggerText, color: value ? "#1e293b" : "#94a3b8" }}>{displayLabel}</span>
        <span style={S.caret(open)}>▼</span>
      </div>
      {open && (
        <div style={{ ...S.menu, maxHeight: 220, overflowY: "auto" }}>
          {options.map((opt) => {
            const v = opt.value ?? opt;
            const l = opt.label ?? opt;
            const isSelected = v === value;
            return (
              <div
                key={v}
                onClick={() => { onChange(v); setOpen(false); }}
                style={{
                  ...S.option,
                  background: isSelected ? "#eef2ff" : "transparent",
                  color: isSelected ? "#4F46E5" : "#1e293b",
                  fontWeight: isSelected ? 600 : 500,
                }}
                onMouseEnter={(e) => { if (!isSelected) e.currentTarget.style.background = "#f1f5f9"; }}
                onMouseLeave={(e) => { if (!isSelected) e.currentTarget.style.background = "transparent"; }}
              >
                {l}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ── MultiSelectDropdown with Select All ───────────────────────────────────────
// Used for Market Filter and Product Filter
function MultiSelectDropdown({ value, onChange, options, placeholder = "Select" }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useClickOutside(ref, () => setOpen(false));

  const allSelected = value.length === options.length;
  const someSelected = value.length > 0 && !allSelected;

  const displayLabel = value.length === 0
    ? placeholder
    : allSelected
    ? `All (${options.length})`
    : value.join(", ");

  const toggleAll = () => onChange(allSelected ? [] : [...options]);
  const toggleOne = (opt) =>
    onChange(value.includes(opt) ? value.filter((v) => v !== opt) : [...value, opt]);

  return (
    <div ref={ref} style={{ position: "relative" }}>
      <div
        onClick={() => setOpen((o) => !o)}
        style={S.trigger(open)}
        onMouseEnter={(e) => { if (!open) e.currentTarget.style.borderColor = "#94a3b8"; }}
        onMouseLeave={(e) => { if (!open) e.currentTarget.style.borderColor = open ? "#4F46E5" : "#e2e8f0"; }}
      >
        <span style={{ ...S.triggerText, color: value.length ? "#1e293b" : "#94a3b8" }}>{displayLabel}</span>
        <span style={S.caret(open)}>▼</span>
      </div>
      {open && (
        <div style={{ ...S.menu, maxHeight: 240, overflowY: "auto" }}>
          {/* Select All row */}
          <label
            style={{ ...S.option, borderBottom: "1px solid #f1f5f9", marginBottom: 4, paddingBottom: 10 }}
            onMouseEnter={(e) => (e.currentTarget.style.background = "#f1f5f9")}
            onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
          >
            {/* Indeterminate-capable checkbox */}
            <span style={{ position: "relative", width: 13, height: 13, flexShrink: 0 }}>
              <input
                type="checkbox"
                checked={allSelected}
                ref={(el) => { if (el) el.indeterminate = someSelected; }}
                onChange={toggleAll}
                style={S.input}
              />
            </span>
            <span style={{ fontWeight: 600, color: "#1e293b" }}>Select All</span>
          </label>
          {options.map((opt) => (
            <label
              key={opt}
              style={S.option}
              onMouseEnter={(e) => (e.currentTarget.style.background = "#f1f5f9")}
              onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
            >
              <input
                type="checkbox"
                checked={value.includes(opt)}
                onChange={() => toggleOne(opt)}
                style={S.input}
              />
              {opt}
            </label>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Filter Toolbar ─────────────────────────────────────────────────────────────
// Styled to exactly match ModelInput.jsx:
//   Label  → fontSize 14px, fontWeight 700, color #64748b, marginBottom 8px (NOT uppercase)
//   Input  → height 35px, borderRadius 8px, minWidth 160px, bg #fcfcfd
//   TA badge → bg #10b981 (green), white text, height 34px, borderRadius 6px
//   Payer/Product → single-select (not multi), displayEmpty "Select"
//   Apply btn → bg #4F46E5, height 34px, borderRadius 6px, fontSize 13px
//   Container → Paper: border 1px #D8DEE8, borderRadius 16px, padding 24px
//               inner flex: gap 24px, alignItems flex-end, flexWrap wrap
function FilterToolbar({ onApply, therapyArea = "HCV" }) {
  const SCENARIOS       = ["Base", "Scenario A", "Scenario B", "Scenario C"];
  const AVAILABLE_MONTHS = [
    { value: "2025-01-01", label: "Jan 25" }, { value: "2025-04-01", label: "Apr 25" },
    { value: "2025-07-01", label: "Jul 25" }, { value: "2025-10-01", label: "Oct 25" },
    { value: "2026-01-01", label: "Jan 26" }, { value: "2026-02-01", label: "Feb 26" },
    { value: "2026-03-01", label: "Mar 26" }, { value: "2026-04-01", label: "Apr 26" },
    { value: "2026-05-01", label: "May 26" }, { value: "2026-06-01", label: "Jun 26" },
    { value: "2026-07-01", label: "Jul 26" }, { value: "2026-08-01", label: "Aug 26" },
    { value: "2026-09-01", label: "Sep 26" }, { value: "2026-10-01", label: "Oct 26" },
    { value: "2026-11-01", label: "Nov 26" }, { value: "2026-12-01", label: "Dec 26" },
  ];
  // Fallbacks match ModelInput.jsx lines 1322-1323
  const PAYER_OPTIONS   = ["Commercial", "Medicare", "Medicaid"];
  const PRODUCT_OPTIONS = ["GILD", "ASGA", "others"];

  const [scenarioName,    setScenarioName]    = useState("Base");
  const [fromDate,        setFromDate]        = useState("2026-01-01");
  const [toDate,          setToDate]          = useState("");
  const [payerFilter,     setPayerFilter]     = useState("");
  const [productFilter,   setProductFilter]   = useState("");

  // To Date options filtered to be strictly after From Date (mirrors ModelInput)
  const toDateOptions = AVAILABLE_MONTHS.filter((m) => m.value > fromDate);

  const handleFromDate = (v) => {
    setFromDate(v);
    setToDate(""); // reset To Date when From changes, exactly as ModelInput does
  };

  const handleApply = () => {
    onApply?.({ therapyArea, scenarioName, fromDate, toDate, payerFilter, productFilter });
  };

  // ── Shared element styles (pixel-exact from ModelInput) ───────────────────
  const lbl = {
    display: "block", marginBottom: 8,
    fontSize: 14, fontWeight: 700, color: "#64748b",
  };
  const inp = {
    height: 35, minWidth: 160, background: "#fcfcfd",
    border: "1px solid #e2e8f0", borderRadius: 8,
    padding: "0 10px 0 12px", fontSize: 13, fontWeight: 500,
    color: "#1e293b", outline: "none", cursor: "pointer",
    boxSizing: "border-box", appearance: "none", WebkitAppearance: "none",
  };
  // Wrapper adds the caret icon via a positioned chevron
  const inpWrap = { position: "relative", display: "inline-block" };
  const caret = {
    position: "absolute", right: 10, top: "50%",
    transform: "translateY(-50%)", pointerEvents: "none",
    fontSize: 9, color: "#94a3b8",
  };

  const Sel = ({ value, onChange, options, placeholder = "Select", disabled = false }) => (
    <div style={inpWrap}>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        style={{
          ...inp,
          paddingRight: 28,
          color: value ? "#1e293b" : "#94a3b8",
          opacity: disabled ? 0.5 : 1,
          cursor: disabled ? "not-allowed" : "pointer",
        }}
        onFocus={(e)  => (e.target.style.borderColor = "#4F46E5")}
        onBlur={(e)   => (e.target.style.borderColor = "#e2e8f0")}
      >
        <option value="" disabled>{placeholder}</option>
        {options.map((o) => {
          const v = o.value ?? o;
          const l = o.label ?? o;
          return <option key={v} value={v}>{l}</option>;
        })}
      </select>
      <span style={caret}>▼</span>
    </div>
  );

  return (
    <div style={{
      background: "#fff", border: "1px solid #D8DEE8", borderRadius: 16,
      padding: 24, display: "flex", alignItems: "flex-end",
      gap: 24, flexWrap: "wrap",
    }}>

      {/* ── Therapeutic Area — green badge, matches ModelInput exactly ── */}
      <div>
        <span style={lbl}>THERAPEUTIC AREA</span>
        <div style={{
          height: 34, padding: "0 16px", display: "flex", alignItems: "center",
          background: "#10b981", borderRadius: 6, minWidth: 100,
        }}>
          <span style={{ fontSize: 13, fontWeight: 600, color: "#fff", whiteSpace: "nowrap" }}>
            {therapyArea}
          </span>
        </div>
      </div>

      {/* ── Scenario Name ── */}
      <div>
        <span style={lbl}>SCENARIO NAME</span>
        <Sel value={scenarioName} onChange={setScenarioName} options={SCENARIOS} />
      </div>

      {/* ── From Date ── */}
      <div>
        <span style={lbl}>FROM DATE</span>
        <Sel value={fromDate} onChange={handleFromDate} options={AVAILABLE_MONTHS} placeholder="Select" />
      </div>

      {/* ── To Date — disabled until From Date chosen, filtered to > From Date ── */}
      <div>
        <span style={lbl}>TO DATE</span>
        <Sel
          value={toDate}
          onChange={setToDate}
          options={toDateOptions}
          placeholder="Select"
          disabled={!fromDate}
        />
      </div>

      {/* ── Payer Filter — single select, matches ModelInput payerFilter ── */}
      <div>
        <span style={lbl}>PAYER FILTER</span>
        <Sel value={payerFilter} onChange={setPayerFilter} options={PAYER_OPTIONS} placeholder="Select" />
      </div>

      {/* ── Product Filter — single select, matches ModelInput productFilter ── */}
      <div>
        <span style={lbl}>PRODUCT FILTER</span>
        <Sel value={productFilter} onChange={setProductFilter} options={PRODUCT_OPTIONS} placeholder="Select" />
      </div>

      {/* ── Apply Filter ── */}
      <button
        onClick={handleApply}
        style={{
          height: 34, background: "#4F46E5", color: "#fff", border: "none",
          borderRadius: 6, padding: "0 18px", fontSize: 13,
          fontWeight: 600, cursor: "pointer", whiteSpace: "nowrap",
          textTransform: "none", letterSpacing: 0,
        }}
        onMouseEnter={(e) => (e.currentTarget.style.background = "#4338ca")}
        onMouseLeave={(e) => (e.currentTarget.style.background = "#4F46E5")}
      >
        Apply Filter
      </button>
    </div>
  );
}

// ── Plotly script loader ───────────────────────────────────────────────────────
function usePlotly() {
  const [ready, setReady] = useState(
    typeof window !== "undefined" && !!window.Plotly
  );
  useEffect(() => {
    if (window.Plotly) { setReady(true); return; }
    const s = document.createElement("script");
    s.src = "https://cdn.jsdelivr.net/npm/plotly.js-dist@2.35.2/plotly.min.js";
    s.onload = () => setReady(true);
    document.head.appendChild(s);
  }, []);
  return ready;
}

// ── Root export ────────────────────────────────────────────────────────────────
export default function MarketEventPage({ onApply, therapyArea = "HCV" }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16, padding: 24, background: "#f8fafc", minHeight: "100vh" }}>
      <FilterToolbar onApply={onApply} therapyArea={therapyArea} />
      <ImpactCurveSection />
    </div>
  );
}