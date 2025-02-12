class MenuDashboard {
    constructor() {
        this.updateInterval = 30000; // 30 seconds
        this.initializeEventListeners();
        this.startAutoUpdate();
    }
    
    async updateMenuStatus() {
        try {
            const response = await fetch('/api/next-menu');
            const data = await response.json();
            
            if (data.error) {
                this.showError(data.error);
                return;
            }
            
            this.updateDisplay(data);
        } catch (error) {
            console.error('Failed to update menu status:', error);
            this.showError('Failed to update menu status');
        }
    }
    
    updateDisplay(data) {
        // Update UI elements
        document.getElementById('nextMenuDate').textContent = 
            new Date(data.send_date).toLocaleDateString();
        document.getElementById('menuSeason').textContent = 
            data.season;
        // ... more UI updates
    }
    
    showError(message) {
        const errorDiv = document.getElementById('errorMessages');
        errorDiv.innerHTML = `
            <div class="alert alert-danger">
                <i class="fas fa-exclamation-circle"></i> ${message}
            </div>
        `;
    }
} 