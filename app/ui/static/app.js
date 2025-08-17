/**
 * Cognitex Frontend Application
 */

// API base URL
const API_BASE_URL = window.location.origin;

// Token management
const TOKEN_KEY = 'cognitex_token';
const USER_KEY = 'cognitex_user';

/**
 * Store authentication token
 */
function storeToken(token) {
    localStorage.setItem(TOKEN_KEY, token);
}

/**
 * Get stored authentication token
 */
function getToken() {
    return localStorage.getItem(TOKEN_KEY);
}

/**
 * Remove authentication token
 */
function clearToken() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
}

/**
 * Store user information
 */
function storeUser(user) {
    localStorage.setItem(USER_KEY, JSON.stringify(user));
}

/**
 * Get stored user information
 */
function getUser() {
    const userStr = localStorage.getItem(USER_KEY);
    return userStr ? JSON.parse(userStr) : null;
}

/**
 * Show status message
 */
function showStatus(message, isError = false) {
    const statusEl = document.getElementById('statusMessage');
    statusEl.textContent = message;
    statusEl.className = `status ${isError ? 'error' : 'success'}`;
    statusEl.style.display = 'block';
    
    // Auto-hide after 5 seconds
    setTimeout(() => {
        statusEl.style.display = 'none';
    }, 5000);
}

/**
 * Show loading spinner
 */
function showLoading(show = true) {
    const loadingEl = document.getElementById('loading');
    const loginSection = document.getElementById('loginSection');
    
    if (show) {
        loadingEl.classList.add('active');
        loginSection.style.display = 'none';
    } else {
        loadingEl.classList.remove('active');
        loginSection.style.display = 'block';
    }
}

/**
 * Display user information
 */
function displayUser(user) {
    const userInfoEl = document.getElementById('userInfo');
    const loginSection = document.getElementById('loginSection');
    
    // Set user data
    document.getElementById('userName').textContent = user.name || 'User';
    document.getElementById('userEmail').textContent = user.email;
    
    if (user.picture) {
        document.getElementById('userAvatar').src = user.picture;
    } else {
        // Use initials as avatar
        const initials = (user.name || user.email).charAt(0).toUpperCase();
        document.getElementById('userAvatar').style.display = 'none';
    }
    
    // Show user info, hide login
    userInfoEl.classList.add('active');
    loginSection.style.display = 'none';
}

/**
 * Hide user information
 */
function hideUser() {
    const userInfoEl = document.getElementById('userInfo');
    const loginSection = document.getElementById('loginSection');
    
    userInfoEl.classList.remove('active');
    loginSection.style.display = 'block';
}

/**
 * Handle Google Sign-In callback
 */
async function handleGoogleSignIn(response) {
    console.log('Google Sign-In response received');
    console.log('Credential:', response.credential ? 'Present' : 'Missing');
    showLoading(true);
    
    try {
        // Send ID token to backend
        const res = await fetch(`${API_BASE_URL}/api/auth/google`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                id_token: response.credential
            })
        });
        
        if (!res.ok) {
            throw new Error('Authentication failed');
        }
        
        const data = await res.json();
        
        // Store token and user
        storeToken(data.token.access_token);
        storeUser(data.user);
        
        // Display user info
        displayUser(data.user);
        showStatus('Successfully signed in!');
        
    } catch (error) {
        console.error('Authentication error:', error);
        showStatus('Failed to sign in. Please try again.', true);
    } finally {
        showLoading(false);
    }
}

/**
 * Verify stored token on page load
 */
async function verifyStoredToken() {
    const token = getToken();
    if (!token) return false;
    
    try {
        const res = await fetch(`${API_BASE_URL}/api/auth/verify`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        if (!res.ok) {
            clearToken();
            return false;
        }
        
        // Token is valid, get user profile
        const profileRes = await fetch(`${API_BASE_URL}/api/auth/me`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        if (profileRes.ok) {
            const user = await profileRes.json();
            storeUser(user);
            displayUser(user);
            return true;
        }
        
    } catch (error) {
        console.error('Token verification error:', error);
        clearToken();
    }
    
    return false;
}

/**
 * Logout user
 */
async function logout() {
    const token = getToken();
    
    if (token) {
        try {
            await fetch(`${API_BASE_URL}/api/auth/logout`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });
        } catch (error) {
            console.error('Logout error:', error);
        }
    }
    
    // Clear local storage
    clearToken();
    
    // Hide user info
    hideUser();
    
    showStatus('Successfully signed out');
}

/**
 * Navigate to dashboard
 */
function goToDashboard() {
    window.location.href = '/dashboard';
}

/**
 * Make authenticated API request
 */
async function apiRequest(endpoint, options = {}) {
    const token = getToken();
    if (!token) {
        throw new Error('No authentication token');
    }
    
    const headers = {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
        ...options.headers
    };
    
    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
        ...options,
        headers
    });
    
    if (response.status === 401) {
        // Token expired or invalid
        clearToken();
        hideUser();
        showStatus('Session expired. Please sign in again.', true);
        throw new Error('Authentication required');
    }
    
    return response;
}

/**
 * Initialize application
 */
async function initApp() {
    console.log('Initializing Cognitex...');
    
    // Check for stored token
    const hasValidToken = await verifyStoredToken();
    
    if (hasValidToken) {
        console.log('Valid session found');
    } else {
        console.log('No valid session, showing login');
    }
    
    // Update Google Client ID from meta tag or environment
    const googleClientId = document.querySelector('meta[name="google-client-id"]')?.content;
    if (googleClientId) {
        document.getElementById('g_id_onload').setAttribute('data-client_id', googleClientId);
    }
}

// Initialize on page load
window.addEventListener('DOMContentLoaded', initApp);

// Export functions for global use
window.handleGoogleSignIn = handleGoogleSignIn;
window.logout = logout;
window.goToDashboard = goToDashboard;