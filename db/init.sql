IF DB_ID('catalog') IS NULL CREATE DATABASE catalog;
GO
IF DB_ID('propagation') IS NULL CREATE DATABASE propagation;
GO
IF SUSER_ID('catalog_user') IS NULL
    CREATE LOGIN catalog_user WITH PASSWORD = '$(CATALOG_DB_PASSWORD)';
GO
IF SUSER_ID('propagation_user') IS NULL
    CREATE LOGIN propagation_user WITH PASSWORD = '$(PROPAGATION_DB_PASSWORD)';
GO
USE catalog;
IF USER_ID('catalog_user') IS NULL CREATE USER catalog_user FOR LOGIN catalog_user;
ALTER ROLE db_owner ADD MEMBER catalog_user;
GO
USE propagation;
IF USER_ID('propagation_user') IS NULL CREATE USER propagation_user FOR LOGIN propagation_user;
ALTER ROLE db_owner ADD MEMBER propagation_user;
GO
