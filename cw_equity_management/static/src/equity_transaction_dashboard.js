import { Component, onMounted, useRef, useState } from "@odoo/owl";
import { Layout } from "@web/search/layout";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { session } from "@web/session";
import { rpc } from "@web/core/network/rpc";

class EquityTransactionDashboard extends Component {
    setup() {
        // Load session info once during setup
        this.sessionInfo = null;

        this.action = useService("action");
        this.orm = useService("orm");

        this.reportTarget = useRef("report_target");

        // Initialize with first day of current year and today's date (same as profit and loss dashboard)
        const today = new Date().toISOString().slice(0, 10);
        const firstDayOfYear = new Date();
        firstDayOfYear.setMonth(0); // January is month 0
        firstDayOfYear.setDate(1);
        const firstDayStr = firstDayOfYear.toISOString().slice(0, 10);

        this.state = useState({
            selectedDateFrom: firstDayStr,
            selectedDateTo: today
        });

        onMounted(async () => {
            // Load session info first
            this.sessionInfo = await rpc("/web/session/get_session_info");
            this.loadReport();
        });
    }


    buildContext() {
        const ctx = this.env.context || {};

        // REAL user language from backend
        const lang = session.bundle_params?.lang || "en_US";
        const langCode = lang.split('_')[0]; // Extract language code (e.g., 'ar' from 'ar_SA')

        // Define RTL languages
        const rtlLanguages = ['ar', 'he', 'fa', 'ur', 'ku', 'dv', 'ha', 'ps', 'sd', 'ug', 'yi'];
        const isRtl = rtlLanguages.includes(langCode);

        const fullContext = {
            ...ctx,
            lang: lang,
            tz: ctx.tz,
            uid: ctx.uid,
            allowed_company_ids: this.sessionInfo?.user_companies?.allowed_company_ids || ctx.allowed_company_ids || [],
            is_rtl: isRtl,  // Add RTL flag to context
        };
        return fullContext;
    }

    async loadReport() {
        try {
            const options = { 
                date_from: this.state.selectedDateFrom,
                date_to: this.state.selectedDateTo
            };
            const context = this.buildContext();

            const params = new URLSearchParams({
                options: JSON.stringify(options),
                context: JSON.stringify(context),
            });

            const reportUrl = `/report/html/cw_equity_management.equity_transaction_report?${params}`;
            const iframe = document.createElement("iframe");
            iframe.src = reportUrl;
            iframe.className = "w-100 border-0";
            iframe.style.height = "90%";
            iframe.style.minHeight = "400px";
            iframe.style.overflow = "auto";

            this.reportTarget.el.innerHTML = "";
            this.reportTarget.el.appendChild(iframe);

            iframe.onload = () => {
            };
        } catch (err) {
            console.error("Error loading report:", err);
            this.reportTarget.el.innerHTML = `<div class="alert alert-danger">Error loading report: ${err}</div>`;
        }
    }

    refreshReport() {
        this.loadReport();
    }

    printReport() {
        try {
            const options = {
                date_from: this.state.selectedDateFrom,
                date_to: this.state.selectedDateTo
            };
            const context = this.buildContext();

            const params = new URLSearchParams({
                options: JSON.stringify(options),
                context: JSON.stringify(context),
            });

            // Construct the URL for the PDF report.
            const reportUrl = `/report/pdf/cw_equity_management.equity_transaction_report_pdf?${params}`;
            // Open the URL in a new tab.
            window.open(reportUrl, '_blank');

        } catch (err) {
            console.error("Error generating Equity Transaction PDF report URL:", err);
        }
    }

    exportReport() {
        try {
            const ctx = encodeURIComponent(JSON.stringify(this.buildContext()));
            const excelUrl = `/report/equity_transaction/excel?date_from=${this.state.selectedDateFrom}&date_to=${this.state.selectedDateTo}&context=${ctx}`;
            // Use hidden link approach for direct download
            const link = document.createElement('a');
            link.href = excelUrl;
            link.style.display = 'none';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        } catch (err) {
            console.error("Error exporting Excel:", err);
            alert("Could not export to Excel. Check console for details.");
        }
    }

    onDateFromChange(ev) {
        const inputValue = ev.target.value;

        // Validate date format (YYYY-MM-DD)
        const dateRegex = /^\d{4}-\d{2}-\d{2}$/;
        if (!dateRegex.test(inputValue)) {
            console.warn("Invalid date format entered:", inputValue);
            // Optionally show a user-friendly error message
            this.displayWarning("Please enter a valid date in YYYY-MM-DD format");
            return;
        }

        // Additional validation to ensure it's a real date
        const dateObj = new Date(inputValue);
        if (isNaN(dateObj.getTime()) || dateObj.toISOString().split('T')[0] !== inputValue) {
            console.warn("Invalid date entered:", inputValue);
            this.displayWarning("Please enter a valid date");
            return;
        }

        this.state.selectedDateFrom = inputValue;
        this.loadReport();
    }

    onDateToChange(ev) {
        const inputValue = ev.target.value;

        // Validate date format (YYYY-MM-DD)
        const dateRegex = /^\d{4}-\d{2}-\d{2}$/;
        if (!dateRegex.test(inputValue)) {
            console.warn("Invalid date format entered:", inputValue);
            // Optionally show a user-friendly error message
            this.displayWarning("Please enter a valid date in YYYY-MM-DD format");
            return;
        }

        // Additional validation to ensure it's a real date
        const dateObj = new Date(inputValue);
        if (isNaN(dateObj.getTime()) || dateObj.toISOString().split('T')[0] !== inputValue) {
            console.warn("Invalid date entered:", inputValue);
            this.displayWarning("Please enter a valid date");
            return;
        }

        this.state.selectedDateTo = inputValue;
        this.loadReport();
    }

    displayWarning(message) {
        // Create a temporary warning element
        const warningDiv = document.createElement("div");
        warningDiv.className = "alert alert-warning";
        warningDiv.style.position = "fixed";
        warningDiv.style.top = "20px";
        warningDiv.style.right = "20px";
        warningDiv.style.zIndex = "9999";
        warningDiv.innerHTML = message;

        document.body.appendChild(warningDiv);

        // Remove the warning after 3 seconds
        setTimeout(() => {
            if (warningDiv.parentNode) {
                warningDiv.parentNode.removeChild(warningDiv);
            }
        }, 3000);
    }
}

EquityTransactionDashboard.template = "cw_equity_management.EquityTransactionDashboard";
EquityTransactionDashboard.components = { Layout };
registry.category("actions").add("cw_equity_management.equity_transaction_dashboard", EquityTransactionDashboard);

export default EquityTransactionDashboard;