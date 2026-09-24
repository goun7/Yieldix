// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/**
 * @title YieldixRevenueLedger
 * @notice Cryptographic settlement ledger for Autonomous B2B Revenue Operations, 
 *         SLA compliance verification, and verifiable 4-KPI performance attestations.
 * @dev Compliant with W3C Verifiable Credentials v2.0 & EAS (Ethereum Attestation Service) schema.
 */
contract YieldixRevenueLedger {
    struct PerformanceReport {
        bytes32 reportDigest;       // SHA-256 hash of the canonical monthly report
        uint64 periodStart;        // Start timestamp of accounting period
        uint64 periodEnd;          // End timestamp of accounting period
        uint32 totalLeads;         // Total inbound leads handled
        uint32 qualifiedSql;       // Sales Qualified Leads produced
        uint32 p95SpeedToLeadSec;  // P95 response latency in seconds
        uint32 costPerLeadScaled;  // CPL in TRY scaled x100 (e.g., 11840 = 118.40 TL)
        uint16 errorRateBps;       // Error rate in Basis Points (1 bps = 0.01%)
        uint16 escalationRateBps;  // Escalation rate in Basis Points
        bool circuitBreakerTripped;// True if dynamic shedding was triggered
        bool verifiedByClient;     // True if counter-signed / accepted by client
    }

    address public owner;
    address public auditor;
    bool public paused;

    // Tenant ID hash => List of monthly performance reports
    mapping(bytes32 => PerformanceReport[]) private _tenantReports;
    
    // Circuit Breaker Event Log: tenantIdHash => componentName => tripCount
    mapping(bytes32 => mapping(bytes32 => uint256)) public componentTripCounts;

    event ReportAttested(
        bytes32 indexed tenantIdHash,
        bytes32 indexed reportDigest,
        uint64 periodStart,
        uint64 periodEnd,
        uint32 qualifiedSql,
        uint32 costPerLeadScaled
    );

    event ReportCounterSigned(bytes32 indexed tenantIdHash, uint256 reportIndex);
    event CircuitBreakerTripped(bytes32 indexed tenantIdHash, bytes32 indexed componentHash, uint64 timestamp);
    event AuditorUpdated(address indexed previousAuditor, address indexed newAuditor);

    modifier onlyOwner() {
        require(msg.sender == owner, "Yieldix: Caller is not owner");
        _;
    }

    modifier onlyAuditor() {
        require(msg.sender == auditor || msg.sender == owner, "Yieldix: Caller is not auditor");
        _;
    }

    modifier whenNotPaused() {
        require(!paused, "Yieldix: Contract is paused");
        _;
    }

    constructor(address _auditor) {
        owner = msg.sender;
        auditor = _auditor;
    }

    function setPaused(bool _paused) external onlyOwner {
        paused = _paused;
    }

    function setAuditor(address _newAuditor) external onlyOwner {
        require(_newAuditor != address(0), "Yieldix: Invalid address");
        emit AuditorUpdated(auditor, _newAuditor);
        auditor = _newAuditor;
    }

    function attestMonthlyReport(
        bytes32 tenantIdHash,
        bytes32 reportDigest,
        uint64 periodStart,
        uint64 periodEnd,
        uint32 totalLeads,
        uint32 qualifiedSql,
        uint32 p95SpeedToLeadSec,
        uint32 costPerLeadScaled,
        uint16 errorRateBps,
        uint16 escalationRateBps,
        bool circuitBreakerTripped
    ) external onlyAuditor whenNotPaused returns (uint256) {
        require(periodEnd > periodStart, "Yieldix: Invalid period");
        require(reportDigest != bytes32(0), "Yieldix: Empty digest");

        PerformanceReport memory report = PerformanceReport({
            reportDigest: reportDigest,
            periodStart: periodStart,
            periodEnd: periodEnd,
            totalLeads: totalLeads,
            qualifiedSql: qualifiedSql,
            p95SpeedToLeadSec: p95SpeedToLeadSec,
            costPerLeadScaled: costPerLeadScaled,
            errorRateBps: errorRateBps,
            escalationRateBps: escalationRateBps,
            circuitBreakerTripped: circuitBreakerTripped,
            verifiedByClient: false
        });

        _tenantReports[tenantIdHash].push(report);
        uint256 index = _tenantReports[tenantIdHash].length - 1;

        emit ReportAttested(
            tenantIdHash,
            reportDigest,
            periodStart,
            periodEnd,
            qualifiedSql,
            costPerLeadScaled
        );

        return index;
    }

    function clientCounterSign(bytes32 tenantIdHash, uint256 reportIndex) external whenNotPaused {
        require(reportIndex < _tenantReports[tenantIdHash].length, "Yieldix: Index out of bounds");
        _tenantReports[tenantIdHash][reportIndex].verifiedByClient = true;
        emit ReportCounterSigned(tenantIdHash, reportIndex);
    }

    function recordCircuitBreakerTrip(bytes32 tenantIdHash, bytes32 componentHash) external onlyAuditor whenNotPaused {
        componentTripCounts[tenantIdHash][componentHash] += 1;
        emit CircuitBreakerTripped(tenantIdHash, componentHash, uint64(block.timestamp));
    }

    function getReportCount(bytes32 tenantIdHash) external view returns (uint256) {
        return _tenantReports[tenantIdHash].length;
    }

    function getReport(bytes32 tenantIdHash, uint256 index) external view returns (PerformanceReport memory) {
        require(index < _tenantReports[tenantIdHash].length, "Yieldix: Index out of bounds");
        return _tenantReports[tenantIdHash][index];
    }
}
