import { useEffect, useRef, useState } from "react";
import { apiService, type Playlist } from "../services/api";
import "./EditPlaylistInfo.css";

interface EditPlaylistInfoProps {
  playlist: Playlist;
  onClose: () => void;
  onSaved: (updated: Playlist) => void;
}

/**
 * Modal to edit a playlist's name + description. Saves via the backend
 * (PUT /api/playlists/{id}, which writes through to Spotify) and hands the
 * refreshed playlist back to the caller. Dismiss with Cancel or Escape.
 */
function EditPlaylistInfo({
  playlist,
  onClose,
  onSaved,
}: EditPlaylistInfoProps) {
  const [name, setName] = useState(playlist.name);
  const [description, setDescription] = useState(playlist.description ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const nameRef = useRef<HTMLInputElement>(null);

  // Focus the name field on open; close on Escape.
  useEffect(() => {
    nameRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  const dirty =
    name !== playlist.name || description !== (playlist.description ?? "");

  const handleSave = async () => {
    if (!name.trim()) {
      setError("Name can't be empty.");
      return;
    }
    try {
      setSaving(true);
      setError(null);
      const updated = await apiService.updatePlaylistDetails(playlist.id, {
        name: name.trim(),
        description,
      });
      onSaved(updated);
      onClose();
    } catch {
      setError("Failed to save. Try again.");
      setSaving(false);
    }
  };

  return (
    <div className="edit-playlist-overlay">
      <div
        className="edit-playlist-dialog"
        role="dialog"
        aria-modal="true"
        aria-label="Edit playlist info"
      >
        <h2 className="edit-playlist-title">Edit playlist info</h2>

        <label className="edit-playlist-label" htmlFor="edit-pl-name">
          Name
        </label>
        <input
          id="edit-pl-name"
          ref={nameRef}
          className="edit-playlist-input"
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          maxLength={100}
        />

        <label className="edit-playlist-label" htmlFor="edit-pl-desc">
          Description
        </label>
        <textarea
          id="edit-pl-desc"
          className="edit-playlist-textarea"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          rows={3}
          maxLength={300}
        />

        {error && <div className="edit-playlist-error">{error}</div>}

        <div className="edit-playlist-actions">
          <button
            type="button"
            className="edit-playlist-cancel"
            onClick={onClose}
            disabled={saving}
          >
            Cancel
          </button>
          <button
            type="button"
            className="edit-playlist-save"
            onClick={handleSave}
            disabled={saving || !dirty || !name.trim()}
          >
            {saving ? "Saving…" : "Save"}
          </button>
        </div>
      </div>
    </div>
  );
}

export default EditPlaylistInfo;
