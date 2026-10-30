/**
 * ShareLoop Client-Side Interactive Logic
 */

document.addEventListener('DOMContentLoaded', function () {
  // 1. Auto-dismiss flash alerts after 6 seconds
  const alerts = document.querySelectorAll('.alert-dismissible');
  alerts.forEach(function (alert) {
    setTimeout(function () {
      const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
      if (bsAlert) {
        bsAlert.close();
      }
    }, 6000);
  });

  // 2. Dynamic Rental Cost Calculator (on listing detail pages)
  const rentStartDate = document.getElementById('rental_start_date');
  const rentEndDate = document.getElementById('rental_end_date');
  const dailyRateElem = document.getElementById('daily_rate_val');
  const depositElem = document.getElementById('security_deposit_val');
  const commPctElem = document.getElementById('comm_pct_val');

  if (rentStartDate && rentEndDate && dailyRateElem) {
    const today = new Date().toISOString().split('T')[0];
    rentStartDate.min = today;
    rentEndDate.min = today;

    function updateRentalCostPreview() {
      if (!rentStartDate.value || !rentEndDate.value) return;

      const start = new Date(rentStartDate.value);
      const end = new Date(rentEndDate.value);

      if (end < start) {
        rentEndDate.value = rentStartDate.value;
      }

      const diffTime = Math.abs(new Date(rentEndDate.value) - new Date(rentStartDate.value));
      const days = Math.ceil(diffTime / (1000 * 60 * 60 * 24)) + 1;

      const dailyRate = parseFloat(dailyRateElem.dataset.rate || '0');
      const deposit = parseFloat(depositElem ? depositElem.dataset.deposit || '0' : '0');
      const commPct = parseFloat(commPctElem ? commPctElem.dataset.pct || '5.0' : '5.0') / 100.0;

      const rentalFee = days * dailyRate;
      const platformFee = Math.round(rentalFee * commPct * 100) / 100;
      const totalPayable = rentalFee + deposit + platformFee;

      const calcDays = document.getElementById('calc_days');
      const calcRentalFee = document.getElementById('calc_rental_fee');
      const calcPlatformFee = document.getElementById('calc_platform_fee');
      const calcTotal = document.getElementById('calc_total_payable');

      if (calcDays) calcDays.textContent = days + (days === 1 ? ' day' : ' days');
      if (calcRentalFee) calcRentalFee.textContent = '₹' + rentalFee.toFixed(2);
      if (calcPlatformFee) calcPlatformFee.textContent = '₹' + platformFee.toFixed(2);
      if (calcTotal) calcTotal.textContent = '₹' + totalPayable.toFixed(2);
    }

    rentStartDate.addEventListener('change', function () {
      rentEndDate.min = rentStartDate.value;
      updateRentalCostPreview();
    });
    rentEndDate.addEventListener('change', updateRentalCostPreview);
  }

  // 3. Image preview on listing form upload
  const imageInput = document.getElementById('id_image');
  const previewContainer = document.getElementById('image_preview_box');
  if (imageInput && previewContainer) {
    imageInput.addEventListener('change', function () {
      previewContainer.innerHTML = '';
      if (this.files && this.files[0]) {
        const reader = new FileReader();
        reader.onload = function (e) {
          const img = document.createElement('img');
          img.src = e.target.result;
          img.className = 'img-thumbnail';
          img.style.maxHeight = '180px';
          previewContainer.appendChild(img);
        };
        reader.readAsDataURL(this.files[0]);
      }
    });
  }

  // 4. Safe confirmation modals
  document.querySelectorAll('[data-confirm]').forEach(function (button) {
    button.addEventListener('click', function (e) {
      const message = this.getAttribute('data-confirm') || 'Are you sure you want to proceed?';
      if (!confirm(message)) {
        e.preventDefault();
      }
    });
  });

  // 5. Accessible User Profile & Admin Dropdown Navigation
  const userDropdownBtn = document.getElementById('userProfileDropdown');
  const userDropdownMenu = document.querySelector('.sl-user-dropdown-menu');
  const userDropdownContainer = document.querySelector('.sl-user-dropdown');

  if (userDropdownBtn && userDropdownMenu) {
    const getDropdownInstance = function () {
      if (typeof bootstrap !== 'undefined' && bootstrap.Dropdown) {
        return bootstrap.Dropdown.getOrCreateInstance(userDropdownBtn);
      }
      return null;
    };

    const closeDropdown = function () {
      const bsDropdown = getDropdownInstance();
      if (bsDropdown) {
        bsDropdown.hide();
      } else {
        userDropdownMenu.classList.remove('show');
        userDropdownBtn.setAttribute('aria-expanded', 'false');
      }
    };

    // Close on Escape key and return focus to trigger button
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' || e.key === 'Esc') {
        const isExpanded = userDropdownBtn.getAttribute('aria-expanded') === 'true' || userDropdownMenu.classList.contains('show');
        if (isExpanded) {
          closeDropdown();
          userDropdownBtn.focus();
        }
      }
    });

    // Close dropdown when selecting an item
    userDropdownMenu.querySelectorAll('.dropdown-item').forEach(function (item) {
      item.addEventListener('click', function () {
        closeDropdown();
      });
    });

    // Keyboard navigation (ArrowDown, ArrowUp, Home, End)
    if (userDropdownContainer) {
      userDropdownContainer.addEventListener('keydown', function (e) {
        const items = Array.from(userDropdownMenu.querySelectorAll('.dropdown-item:not([disabled])'));
        if (!items.length) return;

        const activeElem = document.activeElement;
        const currentIndex = items.indexOf(activeElem);

        if (e.key === 'ArrowDown') {
          e.preventDefault();
          if (activeElem === userDropdownBtn) {
            const bsDropdown = getDropdownInstance();
            if (bsDropdown) bsDropdown.show();
            items[0].focus();
          } else if (currentIndex === -1 || currentIndex === items.length - 1) {
            items[0].focus();
          } else {
            items[currentIndex + 1].focus();
          }
        } else if (e.key === 'ArrowUp') {
          e.preventDefault();
          if (activeElem === userDropdownBtn) {
            const bsDropdown = getDropdownInstance();
            if (bsDropdown) bsDropdown.show();
            items[items.length - 1].focus();
          } else if (currentIndex <= 0) {
            items[items.length - 1].focus();
          } else {
            items[currentIndex - 1].focus();
          }
        } else if (e.key === 'Home' && currentIndex !== -1) {
          e.preventDefault();
          items[0].focus();
        } else if (e.key === 'End' && currentIndex !== -1) {
          e.preventDefault();
          items[items.length - 1].focus();
        }
      });
    }

    // Dismiss when clicking outside the dropdown container
    document.addEventListener('click', function (e) {
      if (userDropdownContainer && !userDropdownContainer.contains(e.target)) {
        const isExpanded = userDropdownBtn.getAttribute('aria-expanded') === 'true' || userDropdownMenu.classList.contains('show');
        if (isExpanded) {
          closeDropdown();
        }
      }
    });
  }
});
