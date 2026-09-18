// Small helper for interactive elements that render as <div>/<li>/<tr> instead
// of <button> because they need block/table layout — spreading this keeps
// them keyboard-operable (Enter/Space) and exposes them to assistive tech
// as buttons, instead of only reacting to a mouse click.
export function clickableProps(onClick) {
  return {
    role: "button",
    tabIndex: 0,
    onClick,
    onKeyDown: (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        onClick(event);
      }
    },
  };
}
