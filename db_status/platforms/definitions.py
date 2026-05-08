"""
Platform definitions — all supported database types.
Covers: MSSQL, Oracle, PostgreSQL, MySQL, MongoDB, SAP HANA,
        MS Exchange, AWS RDS (all variants), Azure SQL, GCP SQL,
        DB2, Cassandra
"""

# ============================================================
# CANDIDATE FIELDS — For Smart Query Builder
# ============================================================

MSSQL_CANDIDATE_FIELDS = [
    "isRelic",
    "isLogShippingSecondary",
    "isMount",
    "isOnline",
    "recoveryModel",
    "unprotectableReasons",
    "slaPauseStatus",
    "copyOnly",
    "dagId",
    "hasPermissions",
    "hostLogRetention",
    "logBackupFrequencyInSeconds",
    "logBackupRetentionInHours",
    "replicatedObjectCount",
    "onDemandSnapshotCount",
    "cluster { id name }",
    "configuredSlaDomain { id name }",
    "effectiveSlaDomain { id name }",
    "effectiveSlaSourceObject { fid name objectType }",
    "effectiveRetentionSlaDomain { id name }",
    "pendingSla { id name }",
    "physicalPath { fid name objectType }",
    "logicalPath { fid name objectType }",
    "oldestSnapshot { id date }",
    "newestSnapshot { id date }",
    "newestArchivedSnapshot { id date }",
    "newestReplicatedSnapshot { id date }",
    "newestIndexedSnapshot { id date }",
    "latestUserNote { userNote time }",
]

ORACLE_CANDIDATE_FIELDS = [
    "isRelic",
    "onDemandSnapshotCount",
    "replicatedObjectCount",
    "slaPauseStatus",
    "cluster { id name }",
    "configuredSlaDomain { id name }",
    "effectiveRetentionSlaDomain { id name }",
    "effectiveSlaDomain { id name }",
    "effectiveSlaSourceObject { fid name objectType }",
    "pendingSla { id name }",
    "physicalPath { fid name objectType }",
    "logicalPath { fid name objectType }",
    "oldestSnapshot { id date }",
    "newestArchivedSnapshot { id date }",
    "newestReplicatedSnapshot { id date }",
    "latestUserNote { userNote time }",
]

POSTGRES_CANDIDATE_FIELDS = [
    "isRelic",
    "slaPauseStatus",
    "cluster { id name }",
    "configuredSlaDomain { id name }",
    "effectiveSlaDomain { id name }",
    "effectiveSlaSourceObject { fid name objectType }",
    "effectiveRetentionSlaDomain { id name }",
    "pendingSla { id name }",
    "physicalPath { fid name objectType }",
    "logicalPath { fid name objectType }",
    "oldestSnapshot { id date }",
    "newestSnapshot { id date }",
    "newestArchivedSnapshot { id date }",
    "newestReplicatedSnapshot { id date }",
    "latestUserNote { userNote time }",
]

MYSQL_CANDIDATE_FIELDS = [
    "isRelic",
    "slaPauseStatus",
    "cluster { id name }",
    "configuredSlaDomain { id name }",
    "effectiveSlaDomain { id name }",
    "effectiveSlaSourceObject { fid name objectType }",
    "effectiveRetentionSlaDomain { id name }",
    "pendingSla { id name }",
    "physicalPath { fid name objectType }",
    "logicalPath { fid name objectType }",
    "oldestSnapshot { id date }",
    "newestSnapshot { id date }",
    "newestIndexedSnapshot { id date }",
    "latestUserNote { userNote time }",
]

MONGO_SOURCE_CANDIDATE_FIELDS = [
    "isRelic",
    "slaPauseStatus",
    "cluster { id name }",
    "configuredSlaDomain { id name }",
    "effectiveSlaDomain { id name }",
    "effectiveSlaSourceObject { fid name objectType }",
    "physicalPath { fid name objectType }",
    "logicalPath { fid name objectType }",
    "oldestSnapshot { id date }",
    "newestSnapshot { id date }",
]

MONGO_DATABASE_CANDIDATE_FIELDS = [
    "isRelic",
    "slaPauseStatus",
    "cluster { id name }",
    "configuredSlaDomain { id name }",
    "effectiveSlaDomain { id name }",
    "effectiveSlaSourceObject { fid name objectType }",
    "physicalPath { fid name objectType }",
    "logicalPath { fid name objectType }",
    "oldestSnapshot { id date }",
    "newestSnapshot { id date }",
]

MONGO_COLLECTION_CANDIDATE_FIELDS = [
    "isRelic",
    "slaPauseStatus",
    "cluster { id name }",
    "configuredSlaDomain { id name }",
    "effectiveSlaDomain { id name }",
    "effectiveSlaSourceObject { fid name objectType }",
    "physicalPath { fid name objectType }",
    "logicalPath { fid name objectType }",
    "oldestSnapshot { id date }",
    "newestSnapshot { id date }",
]

SAP_HANA_CANDIDATE_FIELDS = [
    "isRelic",
    "slaPauseStatus",
    "cluster { id name }",
    "configuredSlaDomain { id name }",
    "effectiveSlaDomain { id name }",
    "effectiveSlaSourceObject { fid name objectType }",
    "pendingSla { id name }",
    "physicalPath { fid name objectType }",
    "logicalPath { fid name objectType }",
    "oldestSnapshot { id date }",
    "latestUserNote { userNote time }",
]

DB2_CANDIDATE_FIELDS = [
    "isRelic",
    "slaPauseStatus",
    "cluster { id name }",
    "configuredSlaDomain { id name }",
    "effectiveSlaDomain { id name }",
    "effectiveSlaSourceObject { fid name objectType }",
    "pendingSla { id name }",
    "physicalPath { fid name objectType }",
    "logicalPath { fid name objectType }",
    "oldestSnapshot { id date }",
    "latestUserNote { userNote time }",
]

EXCHANGE_CANDIDATE_FIELDS = [
    "isRelic",
    "slaPauseStatus",
    "cluster { id name }",
    "configuredSlaDomain { id name }",
    "effectiveSlaDomain { id name }",
    "effectiveSlaSourceObject { fid name objectType }",
    "pendingSla { id name }",
    "physicalPath { fid name objectType }",
    "logicalPath { fid name objectType }",
    "oldestSnapshot { id date }",
    "latestUserNote { userNote time }",
]

AZURE_SQL_DB_CANDIDATE_FIELDS = [
    "isRelic",
    "databaseName",
    "serviceTier",
    "slaPauseStatus",
    "configuredSlaDomain { id name }",
    "effectiveRetentionSlaDomain { id name }",
    "effectiveSlaDomain { id name }",
    "effectiveSlaSourceObject { fid name objectType }",
    "rscNativeObjectPendingSla { id name }",
    "physicalPath { fid name objectType }",
    "logicalPath { fid name objectType }",
    "newestIndexedSnapshot { id date }",
]

AZURE_SQL_MI_CANDIDATE_FIELDS = [
    "isRelic",
    "databaseName",
    "serviceTier",
    "slaPauseStatus",
    "configuredSlaDomain { id name }",
    "effectiveRetentionSlaDomain { id name }",
    "effectiveSlaDomain { id name }",
    "effectiveSlaSourceObject { fid name objectType }",
    "rscNativeObjectPendingSla { id name }",
    "physicalPath { fid name objectType }",
    "logicalPath { fid name objectType }",
    "newestIndexedSnapshot { id date }",
]

GCP_CLOUD_SQL_CANDIDATE_FIELDS = [
    "nativeName",
    "isRelic",
    "cloudNativeId",
    "databaseVersion",
    "instanceTier",
    "region",
    "state",
    "storageSize",
    "zone",
    "slaPauseStatus",
    "configuredSlaDomain { id name }",
    "effectiveRetentionSlaDomain { id name }",
    "effectiveSlaDomain { id name }",
    "effectiveSlaSourceObject { fid name objectType }",
    "rscNativeObjectPendingSla { id name }",
    "physicalPath { fid name objectType }",
    "logicalPath { fid name objectType }",
    "newestIndexedSnapshot { id date }",
]

AWS_RDS_CANDIDATE_FIELDS = [
    "nativeName",
    "isRelic",
    "dbEngine",
    "dbInstanceClass",
    "region",
    "vpcId",
    "allocatedStorageInGibi",
    "dbiResourceId",
    "status",
    "slaPauseStatus",
    "configuredSlaDomain { id name }",
    "effectiveRetentionSlaDomain { id name }",
    "effectiveSlaDomain { id name }",
    "effectiveSlaSourceObject { fid name objectType }",
    "rscNativeObjectPendingSla { id name }",
    "physicalPath { fid name objectType }",
    "logicalPath { fid name objectType }",
    "newestSnapshot { id date }",
    "oldestSnapshot { id date }",
]

AWS_AURORA_CANDIDATE_FIELDS = [
    "nativeName",
    "isRelic",
    "dbEngine",
    "region",
    "status",
    "slaPauseStatus",
    "configuredSlaDomain { id name }",
    "effectiveRetentionSlaDomain { id name }",
    "effectiveSlaDomain { id name }",
    "effectiveSlaSourceObject { fid name objectType }",
    "rscNativeObjectPendingSla { id name }",
    "physicalPath { fid name objectType }",
    "logicalPath { fid name objectType }",
    "newestSnapshot { id date }",
    "oldestSnapshot { id date }",
]

CASSANDRA_KEYSPACE_CANDIDATE_FIELDS = [
    "cluster { id name }",
    "effectiveSlaDomain { id name }",
]

# ============================================================
# PLATFORM LIST
# ============================================================
PLATFORMS = [
    # --- On-prem / CDM-managed ---
    {
        "name": "MSSQL Databases",
        "query": None,
        "query_name": "mssqlDatabases",
        "candidate_fields": MSSQL_CANDIDATE_FIELDS,
        "data_key": "mssqlDatabases",
        "uses_filter": True,
        "has_events": True,
    },
    {
        "name": "Oracle Databases",
        "query": None,
        "query_name": "oracleDatabases",
        "candidate_fields": ORACLE_CANDIDATE_FIELDS,
        "data_key": "oracleDatabases",
        "uses_filter": True,
        "has_events": False,
    },
    {
        "name": "SAP HANA Databases",
        "query": None,
        "query_name": "sapHanaDatabases",
        "candidate_fields": SAP_HANA_CANDIDATE_FIELDS,
        "data_key": "sapHanaDatabases",
        "uses_filter": True,
        "has_events": False,
    },
    {
        "name": "Db2 Databases",
        "query": None,
        "query_name": "db2Databases",
        "candidate_fields": DB2_CANDIDATE_FIELDS,
        "data_key": "db2Databases",
        "uses_filter": True,
        "has_events": False,
    },
    {
        "name": "Exchange Databases",
        "query": None,
        "query_name": "exchangeDatabases",
        "candidate_fields": EXCHANGE_CANDIDATE_FIELDS,
        "data_key": "exchangeDatabases",
        "uses_filter": True,
        "has_events": False,
    },
    {
        "name": "PostgreSQL DB Clusters",
        "query": None,
        "query_name": "postgreSQLDbClusters",
        "candidate_fields": POSTGRES_CANDIDATE_FIELDS,
        "data_key": "postgreSQLDbClusters",
        "uses_filter": True,
        "has_events": False,
    },
    {
        "name": "PostgreSQL Databases",
        "query": None,
        "query_name": "postgreSQLDatabases",
        "candidate_fields": POSTGRES_CANDIDATE_FIELDS,
        "data_key": "postgreSQLDatabases",
        "uses_filter": True,
        "has_events": False,
    },
    {
        "name": "MySQL Databases",
        "query": None,
        "query_name": "mysqlDatabases",
        "candidate_fields": MYSQL_CANDIDATE_FIELDS,
        "data_key": "mysqlDatabases",
        "uses_filter": True,
        "has_events": False,
    },

    # --- MongoDB (3 levels) ---
    {
        "name": "MongoDB Sources",
        "query": None,
        "query_name": "mongoSources",
        "candidate_fields": MONGO_SOURCE_CANDIDATE_FIELDS,
        "data_key": "mongoSources",
        "uses_filter": True,
        "has_events": False,
    },
    {
        "name": "MongoDB Databases",
        "query": None,
        "query_name": "mongoDatabases",
        "candidate_fields": MONGO_DATABASE_CANDIDATE_FIELDS,
        "data_key": "mongoDatabases",
        "uses_filter": True,
        "has_events": False,
    },
    {
        "name": "MongoDB Collections",
        "query": None,
        "query_name": "mongoCollections",
        "candidate_fields": MONGO_COLLECTION_CANDIDATE_FIELDS,
        "data_key": "mongoCollections",
        "uses_filter": True,
        "has_events": False,
    },

    # --- Cloud-native: Azure ---
    {
        "name": "Azure SQL Databases",
        "query": None,
        "query_name": "azureSqlDatabases",
        "candidate_fields": AZURE_SQL_DB_CANDIDATE_FIELDS,
        "data_key": "azureSqlDatabases",
        "uses_filter": False,
        "has_events": False,
    },
    {
        "name": "Azure SQL MI Databases",
        "query": None,
        "query_name": "azureSqlManagedInstanceDatabases",
        "candidate_fields": AZURE_SQL_MI_CANDIDATE_FIELDS,
        "data_key": "azureSqlManagedInstanceDatabases",
        "uses_filter": False,
        "has_events": False,
    },

    # --- Cloud-native: GCP ---
    {
        "name": "GCP Cloud SQL Instances",
        "query": None,
        "query_name": "gcpCloudSqlInstances",
        "candidate_fields": GCP_CLOUD_SQL_CANDIDATE_FIELDS,
        "data_key": "gcpCloudSqlInstances",
        "uses_filter": False,
        "has_events": False,
    },

    # --- Cloud-native: AWS ---
    {
        "name": "AWS RDS Instances",
        "query": None,
        "query_name": "awsNativeRdsInstances",
        "candidate_fields": AWS_RDS_CANDIDATE_FIELDS,
        "data_key": "awsNativeRdsInstances",
        "uses_filter": False,
        "has_events": False,
    },
    {
        "name": "AWS Aurora Clusters",
        "query": None,
        "query_name": "awsNativeRdsClusters",
        "candidate_fields": AWS_AURORA_CANDIDATE_FIELDS,
        "data_key": "awsNativeRdsClusters",
        "uses_filter": False,
        "has_events": False,
    },

    # --- Cassandra ---
    {
        "name": "Cassandra Sources",
        "query": None,
        "query_name": "cassandraSources",
        "candidate_fields": [],
        "data_key": "cassandraSources",
        "uses_filter": False,
        "has_events": False,
    },
    {
        "name": "Cassandra Keyspaces",
        "query": None,
        "query_name": "cassandraKeyspaces",
        "candidate_fields": CASSANDRA_KEYSPACE_CANDIDATE_FIELDS,
        "data_key": "cassandraKeyspaces",
        "uses_filter": False,
        "has_events": False,
    },
]
