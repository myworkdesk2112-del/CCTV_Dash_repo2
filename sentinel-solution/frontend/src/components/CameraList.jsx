import { memo } from "react";
import { clickableProps } from "../a11y";

const HEALTH = {
  true: { cls: "camera-list__dot--live", label: "live", title: "Health: live" },
  false: { cls: "camera-list__dot--offline", label: "offline", title: "Health: offline" },
  null: { cls: "camera-list__dot--unknown", label: "unknown", title: "Health unknown — never confirmed live" },
};

function health(cam) {
  return HEALTH[cam.is_healthy === true ? "true" : cam.is_healthy === false ? "false" : "null"];
}

const CameraListRow = memo(function CameraListRow({ cam, selected, onSelect }) {
  const h = health(cam);
  return (
    <li
      className={`camera-list__item ${selected ? "camera-list__item--selected" : ""}`}
      {...clickableProps(() => onSelect(cam.id))}
    >
      {/* The dot alone is colour-only; the sr-only text keeps live/offline/
          unknown readable without colour perception, and title gives
          sighted mouse users the same words as a tooltip. */}
      <span className={`camera-list__dot ${h.cls}`} title={h.title} aria-hidden="true" />
      <span className="sr-only">{h.label}</span>
      <span className="camera-list__id">{cam.id}</span>
      <span className="camera-list__location">{cam.location || "unknown location"}</span>
      {cam.department && <span className="camera-list__department">{cam.department}</span>}
    </li>
  );
});

export default function CameraList({ cameras, selectedCameraId, onSelectCamera }) {
  return (
    <div className="camera-list">
      <h3>Camera registry ({cameras.length})</h3>
      <ul>
        {cameras.map((cam) => (
          <CameraListRow key={cam.id} cam={cam} selected={cam.id === selectedCameraId} onSelect={onSelectCamera} />
        ))}
        {!cameras.length && <li className="camera-list__empty">No cameras onboarded yet.</li>}
      </ul>
    </div>
  );
}
