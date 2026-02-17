// ============================================
// CALENDAR.JS - Calendar Picker Component
// HR Intelligence Platform
// ============================================

class DateRangePicker {
    constructor(options = {}) {
        this.startDate = null;
        this.endDate = null;
        this.currentDate = new Date();
        this.disablePastDates = options.disablePastDates !== false;
        this.disableWeekends = options.disableWeekends || false;
        this.onSelectStart = options.onSelectStart || (() => {});
        this.onSelectEnd = options.onSelectEnd || (() => {});
        this.onSelectRange = options.onSelectRange || (() => {});
    }

    getDaysInMonth(date) {
        return new Date(date.getFullYear(), date.getMonth() + 1, 0).getDate();
    }

    getFirstDayOfMonth(date) {
        return new Date(date.getFullYear(), date.getMonth(), 1).getDay();
    }

    isToday(date) {
        const today = new Date();
        return date.getDate() === today.getDate() &&
               date.getMonth() === today.getMonth() &&
               date.getFullYear() === today.getFullYear();
    }

    isPastDate(date) {
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        return date < today;
    }

    isWeekend(date) {
        const day = date.getDay();
        return day === 0 || day === 6;
    }

    isInRange(date) {
        if (!this.startDate || !this.endDate) return false;
        return date > this.startDate && date < this.endDate;
    }

    isStartDate(date) {
        if (!this.startDate) return false;
        return date.toDateString() === this.startDate.toDateString();
    }

    isEndDate(date) {
        if (!this.endDate) return false;
        return date.toDateString() === this.endDate.toDateString();
    }

    selectDate(date) {
        if (this.disablePastDates && this.isPastDate(date)) {
            return false;
        }
        if (this.disableWeekends && this.isWeekend(date)) {
            return false;
        }

        if (!this.startDate) {
            this.startDate = date;
            this.onSelectStart(date);
            return 'start';
        } else if (!this.endDate) {
            if (date < this.startDate) {
                // Swap if user clicked earlier date
                this.endDate = this.startDate;
                this.startDate = date;
            } else {
                this.endDate = date;
            }
            this.onSelectEnd(date);
            this.onSelectRange(this.startDate, this.endDate);
            return 'end';
        } else {
            // Reset: start new selection
            this.startDate = date;
            this.endDate = null;
            this.onSelectStart(date);
            return 'start';
        }
    }

    getDayCount() {
        if (!this.startDate || !this.endDate) return 0;
        const diffTime = Math.abs(this.endDate - this.startDate);
        return Math.ceil(diffTime / (1000 * 60 * 60 * 24)) + 1;
    }

    previousMonth() {
        this.currentDate.setMonth(this.currentDate.getMonth() - 1);
    }

    nextMonth() {
        this.currentDate.setMonth(this.currentDate.getMonth() + 1);
    }

    clearSelection() {
        this.startDate = null;
        this.endDate = null;
    }

    render() {
        const year = this.currentDate.getFullYear();
        const month = this.currentDate.getMonth();
        const daysInMonth = this.getDaysInMonth(this.currentDate);
        const firstDay = this.getFirstDayOfMonth(this.currentDate);
        const monthName = new Date(year, month).toLocaleDateString('en-US', { month: 'long', year: 'numeric' });

        let html = `
            <div class="calendar-header">
                <button class="calendar-nav-btn" onclick="window.datePickerInstance.previousMonth(); window.datePickerInstance.updateCalendarDisplay()">←</button>
                <h3 class="calendar-month">${monthName}</h3>
                <button class="calendar-nav-btn" onclick="window.datePickerInstance.nextMonth(); window.datePickerInstance.updateCalendarDisplay()">→</button>
            </div>
            <div class="calendar-weekdays">
                <div class="weekday">Sun</div>
                <div class="weekday">Mon</div>
                <div class="weekday">Tue</div>
                <div class="weekday">Wed</div>
                <div class="weekday">Thu</div>
                <div class="weekday">Fri</div>
                <div class="weekday">Sat</div>
            </div>
            <div class="calendar-days">
        `;

        // Empty cells for days before month starts
        for (let i = 0; i < firstDay; i++) {
            html += '<div class="calendar-day empty"></div>';
        }

        // Days of the month
        for (let day = 1; day <= daysInMonth; day++) {
            const date = new Date(year, month, day);
            const dateStr = date.toISOString().split('T')[0];
            let classes = 'calendar-day';
            let disabled = false;

            if (this.disablePastDates && this.isPastDate(date)) {
                classes += ' disabled';
                disabled = true;
            }

            if (this.disableWeekends && this.isWeekend(date)) {
                classes += ' weekend';
            }

            if (this.isToday(date)) {
                classes += ' today';
            }

            if (this.isStartDate(date)) {
                classes += ' range-start';
            } else if (this.isEndDate(date)) {
                classes += ' range-end';
            } else if (this.isInRange(date)) {
                classes += ' in-range';
            }

            const onclick = disabled ? '' : `onclick="window.datePickerInstance.selectDate(new Date('${dateStr}T00:00:00')); window.datePickerInstance.updateCalendarDisplay();"`;
            html += `<button class="${classes}" ${onclick}>${day}</button>`;
        }

        html += `
            </div>
            <div class="calendar-info">
                ${this.startDate ? `<div class="calendar-selected">Start: ${this.startDate.toDateString()}</div>` : ''}
                ${this.endDate ? `<div class="calendar-selected">End: ${this.endDate.toDateString()}</div>` : ''}
                ${this.startDate && this.endDate ? `<div class="calendar-count">${this.getDayCount()} days selected</div>` : ''}
            </div>
        `;

        return html;
    }
}

// Initialize calendar picker for a container
function initializeDateRangePicker(options = {}) {
    window.datePickerInstance = new DateRangePicker({
        disablePastDates: options.disablePastDates !== false,
        disableWeekends: options.disableWeekends || false,
        onSelectStart: options.onSelectStart || (() => {}),
        onSelectEnd: options.onSelectEnd || (() => {}),
        onSelectRange: options.onSelectRange || (() => {})
    });

    return window.datePickerInstance;
}

// Update calendar display
if (typeof DateRangePicker !== 'undefined') {
    DateRangePicker.prototype.updateCalendarDisplay = function() {
        const container = document.getElementById('calendar-picker');
        if (container) {
            container.innerHTML = this.render();
        }
    };
}

window.DateRangePicker = DateRangePicker;
window.initializeDateRangePicker = initializeDateRangePicker;
