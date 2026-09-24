resource "aws_db_subnet_group" "aegis" {
  name       = "aegis-${var.environment}-db-subnet-group"
  subnet_ids = aws_subnet.private_db[*].id
}

resource "aws_security_group" "db_sg" {
  name        = "aegis-${var.environment}-db-sg"
  description = "PostgreSQL Access from App Subnets"
  vpc_id      = aws_vpc.aegis_vpc.id

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    cidr_blocks     = aws_subnet.private_app[*].cidr_block
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_db_instance" "postgres" {
  identifier              = "aegis-${var.environment}-db"
  allocated_storage       = 100
  max_allocated_storage   = 1000
  engine                  = "postgres"
  engine_version          = "16.2"
  instance_class          = "db.r6g.xlarge"
  db_name                 = "aegis_db"
  username                = "aegis_admin"
  password                = "PLACEHOLDER_MANAGED_BY_SECRETS_MANAGER"
  db_subnet_group_name    = aws_db_subnet_group.aegis.name
  vpc_security_group_ids  = [aws_security_group.db_sg.id]
  skip_final_snapshot     = false
  final_snapshot_identifier = "aegis-${var.environment}-final-snap"
  backup_retention_period = 35
  storage_encrypted       = true
  multi_az                = true
}
