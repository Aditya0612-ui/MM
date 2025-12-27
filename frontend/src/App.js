import React, { useState } from 'react';
import './App.css';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:5000/api';

function App() {
  const [url, setUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [downloadType, setDownloadType] = useState('single'); // 'single' or 'playlist'

  const downloadVideo = async () => {
    if (!url) {
      setError('Please enter a YouTube URL');
      return;
    }

    setLoading(true);
    setError('');
    setMessage('');

    try {
      if (downloadType === 'playlist') {
        setMessage('Downloading entire playlist... This may take a while.');
        
        // Download playlist with extended timeout
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 7200000); // 2 hour timeout for playlists
        
        const response = await fetch(`${API_URL}/download-playlist`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ url }),
          signal: controller.signal,
        }).finally(() => clearTimeout(timeoutId));

        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.error || 'Failed to download playlist');
        }

        // Get filename from Content-Disposition header
        const contentDisposition = response.headers.get('Content-Disposition');
        let filename = 'playlist.zip';
        if (contentDisposition) {
          const matches = /filename="([^"]+)"/.exec(contentDisposition);
          if (matches && matches[1]) {
            filename = matches[1];
          }
        }

        // Get the blob data
        const blob = await response.blob();
        
        // Create a download link and trigger download
        const downloadUrl = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = downloadUrl;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(downloadUrl);
        
        setMessage('Playlist downloaded successfully as ZIP file!');
      } else {
        setMessage('Downloading video... Please wait, this may take a while for very long videos (20+ hours).');
        
        // Download single video with extended timeout for long videos
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 3600000); // 60 minute timeout for very long videos
        
        const response = await fetch(`${API_URL}/download`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ url, type: 'single' }),
          signal: controller.signal,
        }).finally(() => clearTimeout(timeoutId));

        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.error || 'Failed to download video');
        }

        // Get filename from Content-Disposition header
        const contentDisposition = response.headers.get('Content-Disposition');
        let filename = 'video.mp4';
        if (contentDisposition) {
          const matches = /filename="([^"]+)"/.exec(contentDisposition);
          if (matches && matches[1]) {
            filename = matches[1];
          }
        }

        // Get the blob data
        const blob = await response.blob();
        
        // Create a download link and trigger download
        const downloadUrl = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = downloadUrl;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(downloadUrl);
        
        setMessage('Video downloaded to your device!');
      }
      setError('');
    } catch (err) {
      if (err.name === 'AbortError') {
        setError('Download timeout. The video may be too long or your connection is slow. Please try a shorter video.');
      } else {
        setError(err.message || 'Failed to download');
      }
      setMessage('');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="App">
      <header className="header">
        <div className="header-label">FAST & SIMPLE</div>
        <h1 className="main-title">YouTube Video Downloader</h1>
        <p className="subtitle">
          Paste a YouTube link and download in the highest quality available (up to 4K/8K) with audio.
        </p>
      </header>

      <div className="search-container">
        <label className="input-label">Download Type</label>
        <div style={{ display: 'flex', gap: '15px', marginBottom: '20px', justifyContent: 'center' }}>
          <label style={{ 
            display: 'flex', 
            alignItems: 'center', 
            cursor: 'pointer',
            padding: '10px 20px',
            borderRadius: '8px',
            background: downloadType === 'single' ? '#3b82f6' : '#1f2937',
            transition: 'all 0.3s'
          }}>
            <input
              type="radio"
              value="single"
              checked={downloadType === 'single'}
              onChange={(e) => setDownloadType(e.target.value)}
              style={{ marginRight: '8px' }}
            />
            <span>📹 Single Video</span>
          </label>
          <label style={{ 
            display: 'flex', 
            alignItems: 'center', 
            cursor: 'pointer',
            padding: '10px 20px',
            borderRadius: '8px',
            background: downloadType === 'playlist' ? '#3b82f6' : '#1f2937',
            transition: 'all 0.3s'
          }}>
            <input
              type="radio"
              value="playlist"
              checked={downloadType === 'playlist'}
              onChange={(e) => setDownloadType(e.target.value)}
              style={{ marginRight: '8px' }}
            />
            <span>📋 Playlist</span>
          </label>
        </div>
        
        <label className="input-label">YouTube URL</label>
        <div className="input-row">
          <input
            type="text"
            className="url-input"
            // Start with 's' to match the cursor position in the image if desired, but empty is better for UX
            placeholder="Paste link here..."
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && !loading && url && downloadVideo()}
          />

        </div>

        <button
          className="btn-quick-download"
          onClick={downloadVideo}
          disabled={loading}
        >
          <span>⚡</span> Quick Download {downloadType === 'playlist' ? 'Playlist' : 'Video'} (1080p)
        </button>

        {/* Status Messages */}
        {error && (
          <div style={{ marginTop: '20px', color: '#ef4444', textAlign: 'center' }}>
            {error}
          </div>
        )}

        {/* Success Message */}
        {message && !loading && (
          <div style={{ marginTop: '20px', textAlign: 'center', background: '#064e3b', padding: '15px', borderRadius: '12px' }}>
            <p style={{ color: '#34d399', fontWeight: 'bold' }}>{message}</p>
          </div>
        )}
        {/* Only show downloading message if still loading */}
        {loading && message && (
          <div style={{ marginTop: '20px', textAlign: 'center', color: '#38bdf8' }}>
            {message}
          </div>
        )}
      </div>

      <div className="features-list">
        <div className="feature-pill">
          <i className='bx bx-movie-play'></i>
          <span>Progressive MP4 with audio</span>
        </div>

        <div className="feature-pill">
          <i className='bx bx-user-x'></i>
          <span>No account needed</span>
        </div>
        <div className="feature-pill">
          <i className='bx bx-hd'></i>
          <span>Supports 4K & 8K</span>
        </div>
        <div className="feature-pill">
          <i className='bx bx-rocket'></i>
          <span>Fast Download Speed</span>
        </div>
        <div className="feature-pill">
          <i className='bx bx-block'></i>
          <span>No Ads</span>
        </div>
      </div>

      <div className="info-section">
        <div className="info-card">
          <div className="icon-wrapper">
            <i className='bx bx-cloud-download'></i>
          </div>
          <h3>How to Download</h3>
          <p>simply paste the YouTube video URL into the input field above and click "Quick Download".</p>
        </div>

        <div className="info-card">
          <div className="icon-wrapper">
            <i className='bx bx-rocket'></i>
          </div>
          <h3>Fast & efficient</h3>
          <p>Our tool is optimized for speed, ensuring you get your videos in the highest quality available in no time.</p>
        </div>

        <div className="info-card">
          <div className="icon-wrapper">
            <i className='bx bx-shield-quarter'></i>
          </div>
          <h3>Safe & Secure</h3>
          <p>We do not store any of your data or downloaded videos. Your privacy is our top priority.</p>
        </div>
      </div>
    </div>
  );
}

export default App;
