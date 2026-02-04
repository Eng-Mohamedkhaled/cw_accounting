import { Component, onMounted, useRef, useState } from "@odoo/owl";
import { Layout } from "@web/search/layout";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { session } from "@web/session";
import { rpc } from "@web/core/network/rpc";
import { Dropdown } from "@web/core/dropdown/dropdown";

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
            selectedDateTo: today,
            transactionType: 'withdrawal', // Default to withdrawal transactions
            partners: [],               // Available partners for selection
            selectedPartnerId: null,    // Selected partner ID (null means all partners)
            selectedPartnerName: '',    // Selected partner name for display (empty means all partners)
            filteredPartners: [],       // Filtered partners based on search
            showPartnerDropdown: false  // Flag to show/hide the dropdown
        });

        onMounted(async () => {
            // Load session info first
            this.sessionInfo = await rpc("/web/session/get_session_info");
            await this.loadPartners();  // Load partners first
            this.loadReport();          // Then load the report
        });
    }


    async loadPartners() {
        try {
            // Get the current company ID from the stored session info
            const currentCompanyId = this.sessionInfo.user_companies?.current_company;

            // Query equity owners only
            const partners = await this.orm.searchRead(
                'res.partner',
                [
                    ['is_equity_owner', '=', true],
                    ['active', '=', true]  // Only active partners
                ],
                [
                    'id',
                    'name',
                    'ref'
                ],
                {
                    context: this.sessionInfo.user_context,
                    order: 'name'
                }
            );
            // Update the state with the partners
            this.state.partners = partners;

            return partners;
        } catch (error) {
            console.error('Error loading equity partners for company:', error);
            console.error('Error details:', error.message);
            throw error;
        }
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

            // Add partner_id to options if a specific partner is selected
            if (this.state.selectedPartnerId) {
                options.partner_id = parseInt(this.state.selectedPartnerId);
            }

            // Add transaction_type to options if not 'all'
            if (this.state.transactionType && this.state.transactionType !== 'all') {
                options.transaction_type = this.state.transactionType;
            }

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

            // Add partner_id to options if a specific partner is selected
            if (this.state.selectedPartnerId) {
                options.partner_id = parseInt(this.state.selectedPartnerId);
            }

            // Add transaction_type to options if not 'all'
            if (this.state.transactionType && this.state.transactionType !== 'all') {
                options.transaction_type = this.state.transactionType;
            }

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
            let excelUrl = `/report/equity_transaction/excel?date_from=${this.state.selectedDateFrom}&date_to=${this.state.selectedDateTo}`;

            // Add partner_id to URL if a specific partner is selected
            if (this.state.selectedPartnerId) {
                excelUrl += `&partner_id=${this.state.selectedPartnerId}`;
            }

            // Add transaction_type to URL if not 'all'
            if (this.state.transactionType && this.state.transactionType !== 'all') {
                excelUrl += `&transaction_type=${this.state.transactionType}`;
            }

            const ctx = encodeURIComponent(JSON.stringify(this.buildContext()));
            excelUrl += `&context=${ctx}`;
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

    onPartnerSearchInput(ev) {
        const searchTerm = ev.target.value;
        this.state.selectedPartnerName = searchTerm;

        if (searchTerm.trim() === '') {
            this.state.filteredPartners = [];
            this.state.showPartnerDropdown = false;
        } else {
            // Filter partners based on search term (case-insensitive)
            const lowerSearchTerm = searchTerm.toLowerCase();
            this.state.filteredPartners = this.state.partners.filter(partner => {
                // Check name match
                const nameMatch = partner.name.toLowerCase().includes(lowerSearchTerm);

                // Check ref match (only if ref exists)
                const refMatch = partner.ref && partner.ref.toLowerCase().includes(lowerSearchTerm);

                // Check combined match (only if ref exists)
                let combinedMatch = false;
                if (partner.ref) {
                    combinedMatch = `${partner.ref} - ${partner.name}`.toLowerCase().includes(lowerSearchTerm);
                } else {
                    combinedMatch = partner.name.toLowerCase().includes(lowerSearchTerm);
                }

                return nameMatch || refMatch || combinedMatch;
            });

            this.state.showPartnerDropdown = this.state.filteredPartners.length > 0;
        }
    }

    onPartnerSelect(ev) {
        ev.preventDefault();

        const partnerId = ev.target.getAttribute('data-partner-id');
        const selectedPartner = this.state.partners.find(part => part.id.toString() === partnerId);

        if (selectedPartner) {
            this.state.selectedPartnerId = partnerId;
            // Format the partner name properly - only show ref if it exists
            if (selectedPartner.ref) {
                this.state.selectedPartnerName = `${selectedPartner.ref} - ${selectedPartner.name}`;
            } else {
                this.state.selectedPartnerName = selectedPartner.name;
            }
            this.state.showPartnerDropdown = false;
            this.loadReport();
        }
    }

    onTransactionTypeChange(ev) {
        this.state.transactionType = ev.target.value;
        this.loadReport();
    }

    clearPartnerSelection() {
        this.state.selectedPartnerId = null;
        this.state.selectedPartnerName = '';
        this.state.filteredPartners = [];
        this.state.showPartnerDropdown = false;
        this.loadReport();
    }
}

EquityTransactionDashboard.template = "cw_equity_management.EquityTransactionDashboard";
EquityTransactionDashboard.components = { Layout, Dropdown };
registry.category("actions").add("cw_equity_management.equity_transaction_dashboard", EquityTransactionDashboard);

export default EquityTransactionDashboard;