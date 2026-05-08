"""
Platform definitions — all supported database types.
Snapshot field mappings based on RSC schema introspection discovery.

Key findings from discovery:
- MSSQL uses cdmNewestSnapshot/cdmOldestSnapshot (not newestSnapshot/oldestSnapshot)
- Oracle, SAP HANA, Db2, Exchange use newestSnapshot/oldestSnapshot
- PostgreSQL Databases, MySQL Databases, MongoDB Databases are child objects (no snapshot fields)
- MongoDB Sources have 0 snapshots — protection is at Collection level
- Azure SQL MI newestSnapshot requires backupLocationId arg (returns null without it)
- GCP Cloud SQL, AWS RDS, Azure SQL DB use newestSnapshot/oldestSnapshot
- AWS RDS static query fails validation — use smart discovery instead
"""

# ============================================================
# STATIC QUERIES
# ============================================================

# MSSQL — Uses cdmNewestSnapshot/cdmOldestSnapshot
MSSQL_QUERY = """
query($first: Int!, $after: String, $filter: [Filter!]) {
    mssqlDatabases(first: $first, after: $after, filter: $filter) {
        count
        edges { node {
            id
            name
            isRelic
            isOnline
            recoveryModel
            unprotectableReasons
            slaPauseStatus
            copyOnly
            isLogShippingSecondary
            hasPermissions
            logBackupFrequencyInSeconds
            logBackupRetentionInHours
            hostLogRetention
            replicatedObjectCount
            onDemandSnapshotCount
            cluster { id name }
            configuredSlaDomain { id name }
            effectiveSlaDomain { id name }
            effectiveSlaSourceObject { fid name objectType }
            effectiveRetentionSlaDomain { id name }
            pendingSla { id name }
            physicalPath { fid name objectType }
            logicalPath { fid name objectType }
            cdmOldestSnapshot { id date }
            cdmNewestSnapshot { id date }
            newestArchivedSnapshot { id date }
            newestReplicatedSnapshot { id date }
            newestIndexedSnapshot { id date }
            latestUserNote { userNote time }
        } }
        pageInfo { endCursor hasNextPage }
    }
}
"""

# Oracle — Uses newestSnapshot/oldestSnapshot
ORACLE_QUERY = """
query($first: Int!, $after: String, $filter: [Filter!]) {
    oracleDatabases(first: $first, after: $after, filter: $filter) {
        count
        edges { node {
            id
            name
            isRelic
            slaPauseStatus
            cluster { id name }
            configuredSlaDomain { id name }
            effectiveSlaDomain { id name }
            effectiveSlaSourceObject { fid name objectType }
            effectiveRetentionSlaDomain { id name }
            pendingSla { id name }
            physicalPath { fid name objectType }
            logicalPath { fid name objectType }
            oldestSnapshot { id date }
            newestSnapshot { id date }
            newestArchivedSnapshot { id date }
            newestReplicatedSnapshot { id date }
            latestUserNote { userNote time }
        } }
        pageInfo { endCursor hasNextPage }
    }
}
"""

# SAP HANA — Uses newestSnapshot/oldestSnapshot
SAP_HANA_QUERY = """
query($first: Int!, $after: String, $filter: [Filter!]) {
    sapHanaDatabases(first: $first, after: $after, filter: $filter) {
        count
        edges { node {
            id
            name
            isRelic
            slaPauseStatus
            cluster { id name }
            configuredSlaDomain { id name }
            effectiveSlaDomain { id name }
            effectiveSlaSourceObject { fid name objectType }
            pendingSla { id name }
            physicalPath { fid name objectType }
            logicalPath { fid name objectType }
            oldestSnapshot { id date }
            newestSnapshot { id date }
            newestReplicatedSnapshot { id date }
            latestUserNote { userNote time }
        } }
        pageInfo { endCursor hasNextPage }
    }
}
"""

# DB2 — Uses newestSnapshot/oldestSnapshot
DB2_QUERY = """
query($first: Int!, $after: String, $filter: [Filter!]) {
    db2Databases(first: $first, after: $after, filter: $filter) {
        count
        edges { node {
            id
            name
            isRelic
            slaPauseStatus
            cluster { id name }
            configuredSlaDomain { id name }
            effectiveSlaDomain { id name }
            effectiveSlaSourceObject { fid name objectType }
            pendingSla { id name }
            physicalPath { fid name objectType }
            logicalPath { fid name objectType }
            oldestSnapshot { id date }
            newestSnapshot { id date }
            newestReplicatedSnapshot { id date }
            latestUserNote { userNote time }
        } }
        pageInfo { endCursor hasNextPage }
    }
}
"""

# Exchange — Uses newestSnapshot/oldestSnapshot
EXCHANGE_QUERY = """
query($first: Int!, $after: String, $filter: [Filter!]) {
    exchangeDatabases(first: $first, after: $after, filter: $filter) {
        count
        edges { node {
            id
            name
            isRelic
            slaPauseStatus
            cluster { id name }
            configuredSlaDomain { id name }
            effectiveSlaDomain { id name }
            effectiveSlaSourceObject { fid name objectType }
            pendingSla { id name }
            physicalPath { fid name objectType }
            logicalPath { fid name objectType }
            oldestSnapshot { id date }
            newestSnapshot { id date }
            newestReplicatedSnapshot { id date }
            latestUserNote { userNote time }
        } }
        pageInfo { endCursor hasNextPage }
    }
}
"""

# Azure SQL DB — Uses newestSnapshot/oldestSnapshot
AZURE_SQL_DB_QUERY = """
query($first: Int!, $after: String) {
    azureSqlDatabases(first: $first, after: $after) {
        count
        edges { node {
            id
            name
            isRelic
            databaseName
            serviceTier
            slaPauseStatus
            configuredSlaDomain { id name }
            effectiveRetentionSlaDomain { id name }
            effectiveSlaDomain { id name }
            effectiveSlaSourceObject { fid name objectType }
            rscNativeObjectPendingSla { id name }
            physicalPath { fid name objectType }
            logicalPath { fid name objectType }
            oldestSnapshot { id date }
            newestSnapshot { id date }
        } }
        pageInfo { endCursor hasNextPage }
    }
}
"""

# GCP Cloud SQL — Uses newestSnapshot/oldestSnapshot
GCP_CLOUD_SQL_QUERY = """
query($first: Int!, $after: String) {
    gcpCloudSqlInstances(first: $first, after: $after) {
        count
        edges { node {
            id
            name
            nativeName
            isRelic
            cloudNativeId
            databaseVersion
            instanceTier
            region
            state
            storageSize
            zone
            slaPauseStatus
            configuredSlaDomain { id name }
            effectiveRetentionSlaDomain { id name }
            effectiveSlaDomain { id name }
            effectiveSlaSourceObject { fid name objectType }
            rscNativeObjectPendingSla { id name }
            physicalPath { fid name objectType }
            logicalPath { fid name objectType }
            oldestSnapshot { id date }
            newestSnapshot { id date }
        } }
        pageInfo { endCursor hasNextPage }
    }
}
"""

# ============================================================
# CANDIDATE FIELDS — For Smart Query Builder (dynamic platforms)
# ============================================================

# PostgreSQL DB Clusters — Has newestSnapshot/oldestSnapshot
POSTGRES_CLUSTER_CANDIDATE_FIELDS = [
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
    "newestReplicatedSnapshot { id date }",
    "latestUserNote { userNote time }",
]

# PostgreSQL Databases — NO snapshot fields (child of cluster)
POSTGRES_DB_CANDIDATE_FIELDS = [
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
]

# MySQL Databases — NO snapshot fields (child of instance)
MYSQL_DB_CANDIDATE_FIELDS = [
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
]

# MySQL Instances — Has snapshot fields (parent of MySQL Databases)
MYSQL_INSTANCE_CANDIDATE_FIELDS = [
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
    "cdmNewestSnapshot { id date }",
    "cdmOldestSnapshot { id date }",
]

# MongoDB Sources — newestSnapshot exists but always null (0 snapshots at source level)
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

# MongoDB Databases — NO snapshot fields (child of source)
MONGO_DATABASE_CANDIDATE_FIELDS = [
    "isRelic",
    "slaPauseStatus",
    "cluster { id name }",
    "configuredSlaDomain { id name }",
    "effectiveSlaDomain { id name }",
    "effectiveSlaSourceObject { fid name objectType }",
    "physicalPath { fid name objectType }",
    "logicalPath { fid name objectType }",
]

# MongoDB Collections — Has newestSnapshot/oldestSnapshot
MONGO_COLLECTION_CANDIDATE_FIELDS = [
    "isRelic",
    "slaPauseStatus",
    "cluster { id name }",
    "configuredSlaDomain { id name }",
    "effectiveSlaDomain { id name }",
    "effectiveSlaSourceObject { fid name objectType }",
    "physicalPath { fid name objectType }",
    "logicalPath { fid name objectType }",
    "newestSnapshot { id date }",
    "oldestSnapshot { id date }",
]

# Azure SQL MI — newestSnapshot requires backupLocationId arg (may return null)
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
    "oldestSnapshot { id date }",
    "newestSnapshot { id date }",
    "newestIndexedSnapshot { id date }",
]

# AWS RDS Instances — Smart discovery (static query fails validation on some RSC builds)
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
    "oldestSnapshot { id date }",
    "newestSnapshot { id date }",
]

# AWS Aurora Clusters
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
    "oldestSnapshot { id date }",
    "newestSnapshot { id date }",
]

# Cassandra Keyspaces
CASSANDRA_KEYSPACE_CANDIDATE_FIELDS = [
    "cluster { id name }",
    "effectiveSlaDomain { id name }",
]

# ============================================================
# PLATFORM LIST — Complete Coverage
# ============================================================
PLATFORMS = [
    # -------------------------------------------------------
    # On-prem / CDM-managed (Static Queries)
    # -------------------------------------------------------
    {
        "name": "MSSQL Databases",
        "query": MSSQL_QUERY,
        "query_name": "mssqlDatabases",
        "candidate_fields": [],
        "data_key": "mssqlDatabases",
        "uses_filter": True,
        "has_events": True,
    },
    {
        "name": "Oracle Databases",
        "query": ORACLE_QUERY,
        "query_name": "oracleDatabases",
        "candidate_fields": [],
        "data_key": "oracleDatabases",
        "uses_filter": True,
        "has_events": False,
    },
    {
        "name": "SAP HANA Databases",
        "query": SAP_HANA_QUERY,
        "query_name": "sapHanaDatabases",
        "candidate_fields": [],
        "data_key": "sapHanaDatabases",
        "uses_filter": True,
        "has_events": False,
    },
    {
        "name": "Db2 Databases",
        "query": DB2_QUERY,
        "query_name": "db2Databases",
        "candidate_fields": [],
        "data_key": "db2Databases",
        "uses_filter": True,
        "has_events": False,
    },
    {
        "name": "Exchange Databases",
        "query": EXCHANGE_QUERY,
        "query_name": "exchangeDatabases",
        "candidate_fields": [],
        "data_key": "exchangeDatabases",
        "uses_filter": True,
        "has_events": False,
    },

    # -------------------------------------------------------
    # On-prem (Smart Discovery)
    # -------------------------------------------------------
    {
        "name": "PostgreSQL DB Clusters",
        "query": None,
        "query_name": "postgreSQLDbClusters",
        "candidate_fields": POSTGRES_CLUSTER_CANDIDATE_FIELDS,
        "data_key": "postgreSQLDbClusters",
        "uses_filter": True,
        "has_events": False,
    },
    {
        "name": "PostgreSQL Databases",
        "query": None,
        "query_name": "postgreSQLDatabases",
        "candidate_fields": POSTGRES_DB_CANDIDATE_FIELDS,
        "data_key": "postgreSQLDatabases",
        "uses_filter": True,
        "has_events": False,
    },
    {
        "name": "MySQL Instances",
        "query": None,
        "query_name": "mysqlInstances",
        "candidate_fields": MYSQL_INSTANCE_CANDIDATE_FIELDS,
        "data_key": "mysqlInstances",
        "uses_filter": True,
        "has_events": False,
    },
    {
        "name": "MySQL Databases",
        "query": None,
        "query_name": "mysqlDatabases",
        "candidate_fields": MYSQL_DB_CANDIDATE_FIELDS,
        "data_key": "mysqlDatabases",
        "uses_filter": True,
        "has_events": False,
    },

    # -------------------------------------------------------
    # MongoDB (3 hierarchy levels)
    # -------------------------------------------------------
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

    # -------------------------------------------------------
    # Cloud-native: Azure
    # -------------------------------------------------------
    {
        "name": "Azure SQL Databases",
        "query": AZURE_SQL_DB_QUERY,
        "query_name": "azureSqlDatabases",
        "candidate_fields": [],
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

    # -------------------------------------------------------
    # Cloud-native: GCP
    # -------------------------------------------------------
    {
        "name": "GCP Cloud SQL Instances",
        "query": GCP_CLOUD_SQL_QUERY,
        "query_name": "gcpCloudSqlInstances",
        "candidate_fields": [],
        "data_key": "gcpCloudSqlInstances",
        "uses_filter": False,
        "has_events": False,
    },

    # -------------------------------------------------------
    # Cloud-native: AWS (Smart Discovery — static query fails validation)
    # -------------------------------------------------------
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

    # -------------------------------------------------------
    # Cassandra
    # -------------------------------------------------------
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