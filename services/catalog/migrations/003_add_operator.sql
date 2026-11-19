ALTER TABLE satellites ADD operator NVARCHAR(50) NOT NULL
    CONSTRAINT df_satellites_operator DEFAULT 'unknown';

EXEC('UPDATE satellites SET operator = ''NASA/Roscosmos'' WHERE norad_id = 25544');
EXEC('UPDATE satellites SET operator = ''NASA'' WHERE norad_id = 20580');
EXEC('UPDATE satellites SET operator = ''NOAA'' WHERE norad_id = 33591');
