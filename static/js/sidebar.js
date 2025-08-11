document.addEventListener('DOMContentLoaded', function () {
    const sidebar = document.getElementById('sidebarMenu');
    const sidebarToggle = document.getElementById('sidebarToggle');
    const contentOverlay = document.getElementById('contentOverlay');
    
    if (sidebarToggle) {
        sidebarToggle.addEventListener('click', function () {
            sidebar.classList.toggle('active');
            if (contentOverlay) {
               contentOverlay.style.display = sidebar.classList.contains('active') ? 'block' : 'none';
            }
        });
    }
    if (contentOverlay) {
        contentOverlay.addEventListener('click', function() {
            sidebar.classList.remove('active');
            this.style.display = 'none';
        });
    }
});
