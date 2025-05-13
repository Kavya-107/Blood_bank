// static/js/script.js

document.addEventListener('DOMContentLoaded', function() {
    // Flash message animation
    const flashMessages = document.querySelectorAll('.flash-message');
    
    flashMessages.forEach(message => {
        // Add fade-in effect
        message.style.opacity = '0';
        message.style.transition = 'opacity 0.5s ease-in-out';
        
        setTimeout(() => {
            message.style.opacity = '1';
        }, 100);
        
        // Auto-dismiss after 5 seconds
        setTimeout(() => {
            message.style.opacity = '0';
            setTimeout(() => {
                message.style.display = 'none';
            }, 500);
        }, 5000);
    });
    
    // Password validation for registration forms
    const registerForms = document.querySelectorAll('form');
    
    registerForms.forEach(form => {
        form.addEventListener('submit', function(event) {
            const passwordField = form.querySelector('input[type="password"]');
            
            if (passwordField && passwordField.value.length < 6) {
                event.preventDefault();
                alert('Password must be at least 6 characters long.');
            }
        });
    });
    
    // Blood type compatibility information
    const bloodTypeSelects = document.querySelectorAll('select[name="blood_type"]');
    
    bloodTypeSelects.forEach(select => {
        select.addEventListener('change', function() {
            const bloodType = this.value;
            let infoElement = this.parentElement.querySelector('.blood-type-info');
            
            if (!infoElement) {
                infoElement = document.createElement('small');
                infoElement.className = 'blood-type-info';
                this.parentElement.appendChild(infoElement);
            }
            
            // Show compatibility info
            switch(bloodType) {
                case 'O-':
                    infoElement.textContent = 'Universal donor - can donate to all blood types.';
                    break;
                case 'O+':
                    infoElement.textContent = 'Can donate to O+, A+, B+, and AB+.';
                    break;
                case 'A-':
                    infoElement.textContent = 'Can donate to A-, A+, AB-, and AB+.';
                    break;
                case 'A+':
                    infoElement.textContent = 'Can donate to A+ and AB+.';
                    break;
                case 'B-':
                    infoElement.textContent = 'Can donate to B-, B+, AB-, and AB+.';
                    break;
                case 'B+':
                    infoElement.textContent = 'Can donate to B+ and AB+.';
                    break;
                case 'AB-':
                    infoElement.textContent = 'Can donate to AB- and AB+.';
                    break;
                case 'AB+':
                    infoElement.textContent = 'Can only donate to AB+. Universal recipient.';
                    break;
                default:
                    infoElement.textContent = '';
            }
        });
    });
    
    // Enhance donation form with quantity slider
    const quantityInput = document.getElementById('quantity_ml');
    if (quantityInput) {
        // Create a value display element
        const valueDisplay = document.createElement('div');
        valueDisplay.className = 'quantity-display';
        valueDisplay.textContent = quantityInput.value + ' ml';
        valueDisplay.style.textAlign = 'center';
        valueDisplay.style.marginTop = '0.5rem';
        valueDisplay.style.fontWeight = 'bold';
        
        quantityInput.parentElement.appendChild(valueDisplay);
        
        // Update displayed value when slider changes
        quantityInput.addEventListener('input', function() {
            valueDisplay.textContent = this.value + ' ml';
        });
    }
    
    // Add current date to footer
    const footerYear = document.querySelector('footer p');
    if (footerYear) {
        const currentYear = new Date().getFullYear();
        footerYear.textContent = `© ${currentYear} Blood Bank Management System`;
    }
});