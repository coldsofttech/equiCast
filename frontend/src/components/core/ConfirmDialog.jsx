import Modal from "./Modal.jsx";
import Button from "./Button.jsx";

/**
 * Delete confirmations for accounts/pies — both support a `?force=true`
 * cascade when the target still has children, so `message` carries that
 * nuance in per-call text (see AccountDetailPage/PieDetailPage) rather
 * than this component guessing at it.
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
    <Modal
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
    </Modal>
  );
}

export default ConfirmDialog;
