import React, { useEffect, useState } from "react";
import axios from "axios";
import { Link } from "react-router-dom";
import { ArrowLeft, Save, UserCircle } from "lucide-react";
import { API_URL } from "../config";

function Profile({ token, onProfileUpdated }) {
  const [profile, setProfile] = useState({ email: "", full_name: "", phone: "" });
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    axios.get(`${API_URL}/auth/me`, { headers: { Authorization: `Bearer ${token}` } })
      .then((response) => setProfile(response.data))
      .catch(() => setError("Unable to load your profile."))
      .finally(() => setLoading(false));
  }, [token]);

  const saveProfile = async (event) => {
    event.preventDefault();
    setStatus("");
    setError("");
    setSaving(true);
    try {
      const response = await axios.put(`${API_URL}/auth/profile`, {
        full_name: profile.full_name,
        phone: profile.phone,
      }, { headers: { Authorization: `Bearer ${token}` } });
      setProfile(response.data);
      onProfileUpdated(response.data);
      setStatus("Profile updated successfully.");
    } catch (requestError) {
      setError(requestError.response?.data?.detail || "Unable to update your profile.");
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <section className="profile-page"><p>Loading profile...</p></section>;

  return (
    <section className="profile-page">
      <Link className="profile-back" to="/"><ArrowLeft size={16} /> Back to chat</Link>
      <div className="profile-heading">
        <UserCircle size={42} />
        <div><p className="eyebrow">Account settings</p><h1>Your profile</h1></div>
      </div>
      <form className="profile-form" onSubmit={saveProfile}>
        <label>Email<input type="email" value={profile.email} readOnly /></label>
        <label>Name<input type="text" value={profile.full_name} onChange={(event) => setProfile({ ...profile, full_name: event.target.value })} required /></label>
        <label>Phone number<input type="tel" value={profile.phone} onChange={(event) => setProfile({ ...profile, phone: event.target.value })} required /></label>
        {error && <p className="auth-error">{error}</p>}
        {status && <p className="profile-success">{status}</p>}
        <button className="auth-submit" type="submit" disabled={saving}><Save size={18} />{saving ? "Saving..." : "Save changes"}</button>
      </form>
    </section>
  );
}

export default Profile;
