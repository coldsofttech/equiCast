import Drawer from "./Drawer.jsx";
import Button from "./Button.jsx";

/**
 * Delete confirmations for accounts/pies — both support a `?force=true`
 * cascade when the target still has children, so `message` carries that
 * nuance in per-call text (see AccountDetailPage/PieDetailPage) rather
 * than this component guessing at it. Renders as a Drawer (not Modal) so
 * every delete confirmation in the app is consistent with the accounts
 * table's own add/edit/delete drawers.
 */
function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = "Delete",
  isLoading = false,
  onConfirm,
  onCancel,
}) {
  return (
    <Drawer
      open={open}
      onClose={onCancel}
      title={title}
      footer={
        <>
          <Button variant="secondary" onClick={onCancel} disabled={isLoading}>
            Cancel
          </Button>
          <Button variant="danger" onClick={onConfirm} isLoading={isLoading}>
            {confirmLabel}
          </Button>
        </>
      }
    >
      <p>{message}</p>
    </Drawer>
  );
}

export default ConfirmDialog;
